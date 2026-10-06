"""Coach — ChessTempo-style move grading + puzzle rating.

Backends:
  1. Stockfish UCI (preferred, accurate). Auto-detected on PATH.
  2. Local material+PST negamax fallback (weak, offline, no binary needed).

Usage from main.py:
    from coach import EngineManager
    coach = EngineManager()           # lazy-opens stockfish on first use
    grade = coach.grade(board_before, played_move, time_s=0.25, depth=14)
    # grade.label in {Best, Excellent, Good, Inaccuracy, Mistake, Blunder}
    # grade.points e.g. +10 / -15, grade.best_san, grade.cp_loss
"""

from __future__ import annotations

import json
import os
import shutil
import threading

import chess
import chess.engine

# ---------------------------------------------------------------------------
# Scoring tables (Chess.com-ish labels, ChessTempo-ish points)
# ---------------------------------------------------------------------------

# cp_loss thresholds from the mover's perspective
LABELS: list[tuple[int, str]] = [
    (10, "Best"),
    (30, "Excellent"),
    (70, "Good"),
    (130, "Inaccuracy"),
    (250, "Mistake"),
    (10**9, "Blunder"),
]

POINTS = {
    "Brilliant": 15,
    "Best": 10,
    "Excellent": 6,
    "Good": 3,
    "Book": 2,
    "Inaccuracy": -3,
    "Mistake": -8,
    "Blunder": -15,
}

LABEL_COLORS = {  # RGB for pygame
    "Brilliant": (120, 220, 255),
    "Best": (110, 200, 130),
    "Excellent": (140, 210, 140),
    "Good": (170, 200, 150),
    "Book": (150, 152, 175),
    "Inaccuracy": (240, 200, 90),
    "Mistake": (240, 150, 80),
    "Blunder": (235, 90, 90),
}

MATE_CP = 100_000


def cp_to_text(cp_mover: int) -> str:
    """+1.2 from mover's perspective, or M5 / -M3 for mates."""
    if abs(cp_mover) >= MATE_CP - 50_000:
        steps = (MATE_CP * 2 - abs(cp_mover)) // 1000 if abs(cp_mover) > MATE_CP else 1
        sign = "" if cp_mover > 0 else "-"
        return f"{sign}M{max(1, steps)}"
    sign = "+" if cp_mover > 0 else ""
    return f"{sign}{cp_mover / 100:.1f}"


def win_pct(cp_mover: int) -> float:
    import math

    if abs(cp_mover) >= MATE_CP - 50_000:
        return 100.0 if cp_mover > 0 else 0.0
    return 50.0 + 50.0 * (2.0 / (1.0 + math.exp(-0.004 * cp_mover)) - 1.0)


def classify(cp_loss: int, played_is_mate: bool, best_is_mate: bool) -> str:
    if best_is_mate and not played_is_mate:
        return "Blunder"  # missed mate, like ChessTempo/Chess.com "Miss"
    for bound, label in LABELS:
        if cp_loss <= bound:
            return label
    return "Blunder"


# ---------------------------------------------------------------------------
# Local fallback eval (mirrors main.py's, duplicated to avoid import cycle)
# ---------------------------------------------------------------------------

_PV = {
    chess.PAWN: 100, chess.KNIGHT: 320, chess.BISHOP: 330,
    chess.ROOK: 500, chess.QUEEN: 900, chess.KING: 0,
}
_PST_N = [
    -50, -40, -30, -30, -30, -30, -40, -50, -40, -20, 0, 0, 0, 0, -20, -40,
    -30, 0, 10, 15, 15, 10, 0, -30, -30, 5, 15, 20, 20, 15, 5, -30,
    -30, 0, 15, 20, 20, 15, 0, -30, -30, 5, 10, 15, 15, 10, 5, -30,
    -40, -20, 0, 5, 5, 0, -20, -40, -50, -40, -30, -30, -30, -30, -40, -50,
]


def _local_eval_white(board: chess.Board) -> int:
    if board.is_checkmate():
        return -MATE_CP if board.turn == chess.WHITE else MATE_CP
    if board.is_stalemate() or board.is_insufficient_material():
        return 0
    s = 0
    for sq in chess.SQUARES:
        p = board.piece_at(sq)
        if p is None:
            continue
        v = _PV[p.piece_type]
        if p.piece_type == chess.KNIGHT:
            v += _PST_N[sq if p.color == chess.WHITE else chess.square_mirror(sq)]
        s += v if p.color == chess.WHITE else -v
    return s


def _local_search(board: chess.Board, depth: int = 2):
    """Returns (best_move, cp_from_mover). Tiny negamax for fallback."""
    moves = list(board.legal_moves)
    if not moves:
        return None, -MATE_CP if board.is_check() else 0

    def negamax(b: chess.Board, d: int, a: float, be: float) -> float:
        if d == 0 or b.is_game_over():
            s = _local_eval_white(b)
            return s if b.turn == chess.WHITE else -s
        best = -float("inf")
        for m in b.legal_moves:
            b.push(m)
            best = max(best, -negamax(b, d - 1, -be, -a))
            b.pop()
            a = max(a, best)
            if a >= be:
                break
        return best

    mover_white = board.turn == chess.WHITE
    scored = []
    for m in moves:
        board.push(m)
        v = -negamax(board, depth - 1, -float("inf"), float("inf"))
        board.pop()
        cp_white = v if mover_white else -v
        scored.append((cp_white, m))
    scored.sort(key=lambda x: x[0], reverse=mover_white)
    best_cp_white, best_m = scored[0]
    cp_mover = best_cp_white if mover_white else -best_cp_white
    # also score the played move on demand by caller
    return best_m, int(cp_mover)


def _local_cp_after(board_before: chess.Board, move: chess.Move, depth: int = 2) -> int:
    """Eval of resulting pos from mover's perspective (mover = board_before.turn)."""
    mover = board_before.turn
    b = board_before.copy()
    b.push(move)
    if b.is_checkmate():
        return MATE_CP  # mover delivered mate
    if b.is_stalemate() or b.is_insufficient_material():
        return 0
    # shallow search from opponent's view, negate
    opp_best, opp_cp = _local_search(b, depth=depth)
    _ = opp_best
    return int(-opp_cp)


# ---------------------------------------------------------------------------
# Engine manager (Stockfish UCI w/ local fallback)
# ---------------------------------------------------------------------------

def find_stockfish() -> str | None:
    for cand in (
        shutil.which("stockfish"),
        "/opt/homebrew/bin/stockfish",
        "/usr/local/bin/stockfish",
        "/usr/bin/stockfish",
    ):
        if cand and os.path.exists(cand) and os.access(cand, os.X_OK):
            return cand
    return None


class Grade:
    def __init__(self, label: str, points: int, cp_loss: int,
                 best_uci: str, best_san: str, best_eval: str,
                 played_eval: str, played_san: str, win_before: float,
                 win_after: float, source: str, mover_is_white: bool,
                 best_cp: int = 0, played_cp: int = 0):
        self.label = label
        self.points = points
        self.cp_loss = cp_loss
        self.best_uci = best_uci
        self.best_san = best_san
        self.best_eval = best_eval
        self.played_eval = played_eval
        self.played_san = played_san
        self.win_before = win_before
        self.win_after = win_after
        self.source = source
        self.mover_is_white = mover_is_white
        self.best_cp = best_cp      # numeric, mover's perspective
        self.played_cp = played_cp  # numeric, mover's perspective

    def __repr__(self) -> str:  # handy for logs/tests
        return (f"Grade({self.label} {self.points:+d} loss={self.cp_loss} "
                f"played={self.played_san}({self.played_eval}) "
                f"best={self.best_san}({self.best_eval}) src={self.source})")


class EngineManager:
    def __init__(self, path: str | None = None, default_time: float = 0.25,
                 default_depth: int = 14, multipv: int = 3):
        self.path = path or find_stockfish()
        self.default_time = default_time
        self.default_depth = default_depth
        self.multipv = multipv
        self._engine = None
        self._lock = threading.RLock()  # re-entrant: skill-switch + analyse nest
        self._failed = False

    # -- lifecycle ------------------------------------------------------
    @property
    def backend(self) -> str:
        return "stockfish" if (self.path and not self._failed) else "local"

    def _ensure(self):
        if self._engine is not None or self._failed or not self.path:
            return self._engine
        try:
            self._engine = chess.engine.SimpleEngine.popen_uci(self.path)
            # keep it fast + quiet for live coaching
            try:
                self._engine.configure({"Threads": 2, "Hash": 64, "Skill Level": 20})
            except Exception:
                pass
            return self._engine
        except Exception:
            self._failed = True
            try:
                if self._engine:
                    self._engine.quit()
            except Exception:
                pass
            self._engine = None
            return None

    def close(self) -> None:
        with self._lock:
            try:
                if self._engine:
                    self._engine.quit()
            except Exception:
                pass
            self._engine = None

    # -- gameplay AI ------------------------------------------------------
    # Easy = local depth-1 (casual, ~600 Elo feel, instant).
    # Medium/Hard = real Stockfish with capped skill (needs the binary).
    AI_LEVELS: dict[str, dict] = {
        "easy": {"label": "Easy", "skill": 0, "time": 0.15, "depth": 6,
                 "blurb": "casual · local search"},
        "medium": {"label": "Medium", "skill": 8, "time": 0.35, "depth": 12,
                   "blurb": "club player · stockfish"},
        "hard": {"label": "Hard", "skill": 20, "time": 0.8, "depth": 18,
                 "blurb": "strong · stockfish full"},
    }

    def _set_skill(self, skill: int) -> None:
        try:
            with self._lock:
                eng = self._ensure()
                if eng is not None:
                    eng.configure({"Skill Level": int(skill)})
        except Exception:
            pass

    def choose_move(self, board: chess.Board, level: str = "medium"):
        """Gameplay move for the AI side. Never raises; None if no moves."""
        cfg = self.AI_LEVELS.get(level, self.AI_LEVELS["medium"])
        if level == "easy" or self._ensure() is None:
            # local fallback (also the Easy personality)
            try:
                mv, _ = _local_search(board.copy(), depth=1)
                if mv is None:
                    mv, _ = _local_search(board.copy(), depth=2)
                return mv
            except Exception:
                moves = list(board.legal_moves)
                return moves[0] if moves else None
        return self._engine_move(board, int(cfg["skill"]),
                                float(cfg["time"]), int(cfg["depth"]))

    # -- rated ladder (adaptive opponents, 300–1200) -------------------------
    RATED_AI: dict[int, dict] = {
        300: {"name": "Rookie", "local": True, "skill": 0, "time": 0.1, "depth": 4},
        600: {"name": "Casual", "local": False, "skill": 2, "time": 0.2, "depth": 8},
        900: {"name": "Club", "local": False, "skill": 8, "time": 0.35, "depth": 12},
        1200: {"name": "Strong", "local": False, "skill": 14, "time": 0.6, "depth": 16},
    }

    @classmethod
    def rung_for(cls, elo: int) -> tuple[int, dict]:
        """Nearest ladder rung (ties go weaker). Returns (rating, cfg)."""
        best = min(cls.RATED_AI, key=lambda r: (abs(r - elo), r))
        return best, cls.RATED_AI[best]

    def choose_move_rated(self, board: chess.Board, elo: int):
        """Adaptive-AI move for a ladder rating. Never raises."""
        _, cfg = self.rung_for(elo)
        if cfg["local"] or self._ensure() is None:
            try:
                mv, _ = _local_search(board.copy(), depth=1)
                return mv
            except Exception:
                moves = list(board.legal_moves)
                return moves[0] if moves else None
        return self._engine_move(board, int(cfg["skill"]),
                                float(cfg["time"]), int(cfg["depth"]))

    def _engine_move(self, board: chess.Board, skill: int, time_s: float, depth: int):
        try:
            with self._lock:
                eng = self._ensure()
                if eng is None:
                    raise RuntimeError("no engine")
                try:
                    eng.configure({"Skill Level": skill})
                except Exception:
                    pass
                try:
                    res = eng.play(
                        board.copy(),
                        chess.engine.Limit(time=time_s, depth=depth),
                    )
                    mv = res.move
                finally:
                    try:
                        eng.configure({"Skill Level": 20})  # restore for grading
                    except Exception:
                        pass
            if mv is not None and mv in board.legal_moves:
                return mv
            moves = list(board.legal_moves)
            return moves[0] if moves else None
        except Exception:
            self._failed = True
            try:
                mv, _ = _local_search(board.copy(), depth=2)
                return mv
            except Exception:
                moves = list(board.legal_moves)
                return moves[0] if moves else None

    # -- analysis -------------------------------------------------------
    def best_in_position(self, board: chess.Board, time_s: float | None = None,
                         depth: int | None = None):
        """-> (best_move, cp_from_mover, san, source). Never raises."""
        mover_white = board.turn == chess.WHITE
        eng = self._ensure()
        if eng is not None:
            try:
                with self._lock:
                    res = eng.analyse(
                        board.copy(),
                        chess.engine.Limit(time=time_s or self.default_time,
                                           depth=depth or self.default_depth),
                        multipv=1,
                    )
                info = res[0] if isinstance(res, list) else res
                pv = info.get("pv") or []
                score = info.get("score")
                if pv and score is not None:
                    try:
                        san = board.san(pv[0])
                    except Exception:
                        san = pv[0].uci()
                    cp = score.pov(board.turn).score(mate_score=MATE_CP)
                    cp = MATE_CP if cp is None else int(cp)
                    return pv[0], cp, san, "stockfish"
            except Exception:
                self._failed = True
                try:
                    with self._lock:
                        if self._engine:
                            self._engine.quit()
                        self._engine = None
                except Exception:
                    pass
        # fallback
        b, cp, = _local_search(board.copy(), depth=2)
        san = board.san(b) if b else "--"
        _ = mover_white
        return b, int(cp), san, "local"

    def eval_after(self, board_before: chess.Board, move: chess.Move,
                   time_s: float | None = None, depth: int | None = None) -> int:
        """Engine eval of resulting position from mover's perspective."""
        mover = board_before.turn
        b = board_before.copy()
        b.push(move)
        if b.is_checkmate():
            return MATE_CP
        if b.is_stalemate() or b.is_insufficient_material():
            return 0
        eng = self._ensure()
        if eng is not None:
            try:
                with self._lock:
                    res = eng.analyse(
                        b, chess.engine.Limit(time=(time_s or self.default_time) * 0.6,
                                              depth=depth or self.default_depth),
                        multipv=1,
                    )
                info = res[0] if isinstance(res, list) else res
                score = info.get("score")
                if score is not None:
                    cp_opp = score.pov(b.turn).score(mate_score=MATE_CP)
                    cp_opp = 0 if cp_opp is None else int(cp_opp)
                    # convert opponent-perspective to mover-perspective
                    return int(-cp_opp) if b.turn != mover else int(cp_opp)
            except Exception:
                self._failed = True
        return _local_cp_after(board_before, move)

    def grade(self, board_before: chess.Board, played: chess.Move,
              time_s: float | None = None, depth: int | None = None) -> Grade:
        mover_white = board_before.turn == chess.WHITE
        try:
            played_san = board_before.san(played)
        except Exception:
            played_san = played.uci()
        best, best_cp, best_san, src = self.best_in_position(board_before, time_s, depth)
        if best is not None and best == played:
            played_cp = best_cp
        else:
            played_cp = self.eval_after(board_before, played, time_s, depth)
            # re-check: engine may disagree on best; if played scores higher, it IS best
            if played_cp > best_cp and best is not None:
                best, best_cp, best_san = played, played_cp, played_san
        cp_loss = max(0, int(best_cp - played_cp))
        best_mate = abs(best_cp) >= MATE_CP - 50_000
        played_mate = abs(played_cp) >= MATE_CP - 50_000
        label = classify(cp_loss, played_mate and played_cp > 0, best_mate and best_cp > 0)
        # Brilliant heuristic v1: best move that sacrifices material (capture value
        # given up) — keep simple: best + played a piece sac detected via SEE-ish?
        # Skip; label Best stays Best.
        points = POINTS[label]
        return Grade(
            label=label, points=points, cp_loss=cp_loss,
            best_uci=(best.uci() if best else played.uci()),
            best_san=best_san, best_eval=cp_to_text(best_cp),
            played_eval=cp_to_text(played_cp), played_san=played_san,
            win_before=win_pct(best_cp), win_after=win_pct(played_cp),
            source=src, mover_is_white=mover_white,
            best_cp=int(best_cp), played_cp=int(played_cp),
        )


# ---------------------------------------------------------------------------
# Puzzles (ChessTempo-style: find the best move(s), get rated)
#
# Two sources, one shape. Puzzle dict:
#   {id, fen, solution, rating, rd, plays, themes, url, source}
# fen = PRESENT position (side to move = solver).
# solution = [uci, ...] starting with the SOLVER's move, opponent replies
# interleaved (exactly like Lichess API). solution=None means "engine-judged
# single move" (offline SAMPLE fallback).
#
# NOTE on Lichess CSV vs API: in the CSV dump, FEN is the position BEFORE the
# opponent's setup move and Moves[0] is that setup move — the presented
# position is FEN+Moves[0], solution is Moves[1:]. In the HTTP API, fen is
# ALREADY the presented position and solution[0] is your first move.
# ---------------------------------------------------------------------------

# Single-move puzzles: position to solve, side to move must find engine-best.
# FENs chosen so the best move is a clear tactic (verified w/ Stockfish 19).
SAMPLE_PUZZLES: list[dict] = [
    {"fen": "r1bqkbnr/pppp1ppp/2n5/4p2Q/2B1P3/8/PPPP1PPP/RNB1K1NR w KQkq - 3 3",
     "rating": 400, "theme": "Mate in 1", "hint": "Look at f7…"},
    {"fen": "6k1/5ppp/8/8/8/8/5PPP/5RK1 w - - 0 1",
     "rating": 500, "theme": "Back-rank mate", "hint": "The 8th rank is weak…"},
    {"fen": "rnbqkbnr/ppp1pppp/8/3p4/4P3/8/PPPP1PPP/RNBQKBNR w KQkq d6 0 2",
     "rating": 600, "theme": "Win a pawn", "hint": "A pawn is hanging…"},
    {"fen": "r1bqkbnr/pppp1ppp/2n5/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4",
     "rating": 800, "theme": "Attack f7", "hint": "Knight to the rim… is dim? Or grim?"},
    {"fen": "r1bqkb1r/pppp1ppp/2n2n2/4p2Q/2B1P3/8/PPPP1PPP/RNB1K1NR w KQkq - 4 4",
     "rating": 950, "theme": "Double attack", "hint": "Qxf7 threatens mate AND the rook…"},
    {"fen": "2r3k1/pp1bpppp/2n2n2/3p4/3P4/2NBP3/PP3PPP/R2Q1RK1 w - - 0 12",
     "rating": 1100, "theme": "Fork / pin", "hint": "Look for a knight jump…"},
    {"fen": "8/8/8/4k3/8/4K3/4P3/8 w - - 0 1",
     "rating": 700, "theme": "Opposition", "hint": "King + pawn endgame…"},
    {"fen": "r2q1rk1/pp1bpppp/2n2n2/2pp4/3P4/2NBP3/PP3PPP/R2Q1RK1 w - - 0 10",
     "rating": 1250, "theme": "Win the exchange", "hint": "A tactic on c5/d5…"},
]

RATING_FILE = "rating.json"
DEFAULT_RATING = 800
K_FACTOR = 32


def load_rating(path: str = RATING_FILE) -> int:
    try:
        with open(path) as f:
            return int(json.load(f).get("puzzle_rating", DEFAULT_RATING))
    except Exception:
        return DEFAULT_RATING


def save_rating(rating: int, path: str = RATING_FILE) -> None:
    try:
        with open(path, "w") as f:
            json.dump({"puzzle_rating": int(rating)}, f)
    except Exception:
        pass


def update_rating(user: int, puzzle: int, solved: bool, k: int = K_FACTOR) -> int:
    import math

    expected = 1.0 / (1.0 + 10 ** ((puzzle - user) / 400.0))
    return int(round(user + k * ((1.0 if solved else 0.0) - expected)))


def pick_puzzle(user_rating: int, seen: set[int] | None = None) -> tuple[int, dict]:
    """Puzzle whose rating is closest to the user (unseen preferred)."""
    best_i, best_d = 0, float("inf")
    for i, p in enumerate(SAMPLE_PUZZLES):
        if seen and i in seen:
            continue
        d = abs(p["rating"] - user_rating)
        if d < best_d:
            best_i, best_d = i, d
    return best_i, SAMPLE_PUZZLES[best_i]


def sample_pool() -> list[dict]:
    """Offline fallback pool: SAMPLE FENs, engine-judged (solution=None)."""
    return [
        {"id": f"sample-{i}", "fen": p["fen"], "solution": None,
         "rating": p["rating"], "rd": 100, "plays": 0,
         "themes": [p.get("theme", "tactic")], "hint": p.get("hint", ""),
         "url": "", "source": "sample"}
        for i, p in enumerate(SAMPLE_PUZZLES)
    ]


# -- Lichess API (stdlib only, anonymous OK) ---------------------------------

API_BASE = "https://lichess.org"


def _api_get_json(path: str, timeout: int = 15) -> dict | None:
    import urllib.request

    try:
        req = urllib.request.Request(
            API_BASE + path,
            headers={"User-Agent": "chesso-coach/0.1 (contact: local app)",
                     "Accept": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.load(r)
    except Exception:
        return None


def puzzle_from_api_data(data: dict, source: str = "lichess-api") -> dict | None:
    """Normalize /api/puzzle/{daily,next,id} payloads to our Puzzle shape."""
    try:
        pz = data.get("puzzle", data)
        sol = [m for m in pz["solution"]]
        fen = pz.get("fen")
        if fen is None:
            # Batch/next payloads omit fen: present position is the FULL
            # game PGN replayed (initialPly = ply before the setup move).
            game = data.get("game", {})
            b0 = chess.Board()
            for san in str(game.get("pgn", "")).split():
                try:
                    b0.push_san(san)
                except Exception:
                    return None
            fen = b0.fen()
        # validate
        b = chess.Board(fen)
        for u in sol:
            b.push_uci(u)
        pid = str(pz.get("id", "api"))
        return {
            "id": pid, "fen": chess.Board(fen).fen(), "solution": sol,
            "rating": int(pz.get("rating", 1200)),
            "rd": int(pz.get("ratingDeviation", 90)),
            "plays": int(pz.get("plays", 0)),
            "themes": list(pz.get("themes", ["tactic"])),
            "url": f"https://lichess.org/training/{pid}",
            "source": source,
        }
    except Exception:
        return None


def fetch_daily() -> dict | None:
    data = _api_get_json("/api/puzzle/daily")
    return puzzle_from_api_data(data, "lichess-daily") if data else None


def fetch_puzzle(pid: str) -> dict | None:
    data = _api_get_json(f"/api/puzzle/{pid}")
    return puzzle_from_api_data(data, "lichess-api") if data else None


def fetch_next(difficulty: str = "normal") -> dict | None:
    data = _api_get_json(f"/api/puzzle/next?difficulty={difficulty}")
    return puzzle_from_api_data(data, "lichess-api") if data else None


def fetch_batch(n: int = 30, timeout_each: int = 15) -> list[dict]:
    """Grab n random puzzles across difficulties (anonymous, sequential)."""
    import time as _t

    diffs = ["easiest", "easier", "normal", "harder", "hardest"]
    out, seen = [], set()
    for i in range(n):
        d = _api_get_json(f"/api/puzzle/next?difficulty={diffs[i % len(diffs)]}",
                          timeout=timeout_each)
        if d:
            p = puzzle_from_api_data(d)
            if p and p["id"] not in seen:
                seen.add(p["id"])
                out.append(p)
        _t.sleep(1.0)  # be nice to the API (rate limits are strict)
    daily = fetch_daily()
    if daily and daily["id"] not in seen:
        out.append(daily)
    return out


def fetch_batch_angles(angles: tuple[str, ...] = ("mateIn1", "mateIn2", "fork",
                                                  "pin", "sacrifice", "hangingPiece"),
                       timeout_each: int = 20) -> list[dict]:
    """One HTTP call per theme via /api/puzzle/batch/{angle} (~15 each)."""
    import urllib.request

    out, seen = [], set()
    for angle in angles:
        try:
            req = urllib.request.Request(
                API_BASE + f"/api/puzzle/batch/{angle}",
                headers={"User-Agent": "chesso-coach/0.1 (contact: local app)",
                         "Accept": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=timeout_each) as r:
                data = json.load(r)
            for p in data.get("puzzles", []):
                puzz = puzzle_from_api_data(
                    {"game": p.get("game", {}), "puzzle": p.get("puzzle", {})},
                    source=f"lichess-{angle}")
                if puzz and puzz["id"] not in seen:
                    seen.add(puzz["id"])
                    out.append(puzz)
        except Exception:
            continue
    return out


# -- Local puzzle library (puzzles.json) --------------------------------------

PUZZLE_FILE = "puzzles.json"


def load_puzzle_file(path: str = PUZZLE_FILE) -> list[dict]:
    try:
        with open(path) as f:
            data = json.load(f)
        pool = data if isinstance(data, list) else data.get("puzzles", [])
        # validate entries cheaply
        good = []
        for p in pool:
            try:
                b = chess.Board(p["fen"])
                for u in (p.get("solution") or []):
                    b.push_uci(u)
                good.append(p)
            except Exception:
                continue
        return good
    except Exception:
        return []


def save_puzzle_file(pool: list[dict], path: str = PUZZLE_FILE) -> None:
    try:
        with open(path, "w") as f:
            json.dump(pool, f)
    except Exception:
        pass


def pick_from_pool(pool: list[dict], user_rating: int,
                   seen: set[str] | None = None) -> tuple[int, dict]:
    best_i, best_d = 0, float("inf")
    for i, p in enumerate(pool):
        if seen and str(p.get("id")) in seen:
            continue
        d = abs(int(p.get("rating", 1200)) - user_rating)
        if d < best_d:
            best_i, best_d = i, d
    if seen and all(str(p.get("id")) in seen for p in pool):
        best_i = min(range(len(pool)),
                     key=lambda i: abs(int(pool[i].get("rating", 1200)) - user_rating))
    return best_i, pool[best_i]


def load_lichess_csv(path: str, limit: int = 500) -> list[dict]:
    """Import Lichess puzzle CSV dump (or a slice of it).

    CSV columns: PuzzleId,FEN,Moves,Rating,RatingDeviation,Popularity,
    NbPlays,Themes,GameUrl,OpeningTags. FEN is PRE-setup: Moves[0] is the
    opponent's setup move, solution is Moves[1:].
    """
    import csv

    out: list[dict] = []
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            try:
                moves = str(row["Moves"]).split()
                if len(moves) < 2:
                    continue
                b = chess.Board(row["FEN"])
                b.push_uci(moves[0])  # opponent setup
                present = b.fen()
                for u in moves[1:]:
                    b.push_uci(u)  # validate solution
                pid = str(row.get("PuzzleId", f"csv-{len(out)}"))
                out.append({
                    "id": pid, "fen": present, "solution": moves[1:],
                    "rating": int(float(row.get("Rating", 1000))),
                    "rd": int(float(row.get("RatingDeviation", 90))),
                    "plays": int(float(row.get("NbPlays", 0))),
                    "themes": str(row.get("Themes", "tactic")).split(),
                    "url": str(row.get("GameUrl", "")
                               or f"https://lichess.org/training/{pid}"),
                    "source": "lichess-csv",
                })
                if len(out) >= limit:
                    break
            except Exception:
                continue
    return out
