"""Chesso — a polished pygame + python-chess game.

Run with:
    uv run python main.py
"""

from __future__ import annotations

import array
import argparse
import math
import threading
import time
import uuid
from dataclasses import dataclass

import chess
import pygame

import coach
import profile as profile_mod

# --------------------------------------------------------------------------
# Config / theme
# --------------------------------------------------------------------------

WIN_W, WIN_H = 1160, 760
BOARD_PX = 680
BOARD_X, BOARD_Y = 32, 40
PANEL_X = BOARD_X + BOARD_PX + 24
PANEL_W = WIN_W - PANEL_X - 24

BG = (21, 22, 33)
BG2 = (26, 27, 40)
PANEL_BG = (32, 33, 50)
LIGHT_SQ = (237, 214, 179)
DARK_SQ = (175, 130, 95)
LIGHT_SQ_HOVER = (243, 224, 192)
DARK_SQ_HOVER = (186, 142, 106)
BORDER = (16, 16, 24)
TEXT = (236, 236, 245)
MUTED = (155, 157, 180)
ACCENT = (129, 182, 255)
GREEN = (110, 200, 130)
YELLOW = (240, 200, 90)
RED = (235, 90, 90)
LAST_MOVE_HL = (205, 210, 60)

GLYPH = {
    (chess.PAWN, chess.WHITE): "\u2659",
    (chess.KNIGHT, chess.WHITE): "\u2658",
    (chess.BISHOP, chess.WHITE): "\u2657",
    (chess.ROOK, chess.WHITE): "\u2656",
    (chess.QUEEN, chess.WHITE): "\u2655",
    (chess.KING, chess.WHITE): "\u2654",
    (chess.PAWN, chess.BLACK): "\u265f",
    (chess.KNIGHT, chess.BLACK): "\u265e",
    (chess.BISHOP, chess.BLACK): "\u265d",
    (chess.ROOK, chess.BLACK): "\u265c",
    (chess.QUEEN, chess.BLACK): "\u265b",
    (chess.KING, chess.BLACK): "\u265a",
}

PIECE_VALUES = {
    chess.PAWN: 100,
    chess.KNIGHT: 320,
    chess.BISHOP: 330,
    chess.ROOK: 500,
    chess.QUEEN: 900,
    chess.KING: 0,
}

# Simple piece-square tables (from white's perspective, a1 = index 0).
# Values in centipawns to nudge development / centre control.
PST_PAWN = [
    0, 0, 0, 0, 0, 0, 0, 0,
    50, 50, 50, 50, 50, 50, 50, 50,
    10, 10, 20, 30, 30, 20, 10, 10,
    5, 5, 10, 25, 25, 10, 5, 5,
    0, 0, 0, 20, 20, 0, 0, 0,
    5, -5, -10, 0, 0, -10, -5, 5,
    5, 10, 10, -20, -20, 10, 10, 5,
    0, 0, 0, 0, 0, 0, 0, 0,
]
PST_KNIGHT = [
    -50, -40, -30, -30, -30, -30, -40, -50,
    -40, -20, 0, 0, 0, 0, -20, -40,
    -30, 0, 10, 15, 15, 10, 0, -30,
    -30, 5, 15, 20, 20, 15, 5, -30,
    -30, 0, 15, 20, 20, 15, 0, -30,
    -30, 5, 10, 15, 15, 10, 5, -30,
    -40, -20, 0, 5, 5, 0, -20, -40,
    -50, -40, -30, -30, -30, -30, -40, -50,
]
PST_BISHOP = [
    -20, -10, -10, -10, -10, -10, -10, -20,
    -10, 0, 0, 0, 0, 0, 0, -10,
    -10, 0, 5, 10, 10, 5, 0, -10,
    -10, 5, 5, 10, 10, 5, 5, -10,
    -10, 0, 10, 10, 10, 10, 0, -10,
    -10, 10, 10, 10, 10, 10, 10, -10,
    -10, 5, 0, 0, 0, 0, 5, -10,
    -20, -10, -10, -10, -10, -10, -10, -20,
]
PST_ROOK = [
    0, 0, 0, 0, 0, 0, 0, 0,
    5, 10, 10, 10, 10, 10, 10, 5,
    -5, 0, 0, 0, 0, 0, 0, -5,
    -5, 0, 0, 0, 0, 0, 0, -5,
    -5, 0, 0, 0, 0, 0, 0, -5,
    -5, 0, 0, 0, 0, 0, 0, -5,
    -5, 0, 0, 0, 0, 0, 0, -5,
    0, 0, 0, 5, 5, 0, 0, 0,
]
PST_QUEEN = [
    -20, -10, -10, -5, -5, -10, -10, -20,
    -10, 0, 0, 0, 0, 0, 0, -10,
    -10, 0, 5, 5, 5, 5, 0, -10,
    -5, 0, 5, 5, 5, 5, 0, -5,
    0, 0, 5, 5, 5, 5, 0, -5,
    -10, 5, 5, 5, 5, 5, 0, -10,
    -10, 0, 5, 0, 0, 0, 0, -10,
    -20, -10, -10, -5, -5, -10, -10, -20,
]
PST_KING = [
    -30, -40, -40, -50, -50, -40, -40, -30,
    -30, -40, -40, -50, -50, -40, -40, -30,
    -30, -40, -40, -50, -50, -40, -40, -30,
    -30, -40, -40, -50, -50, -40, -40, -30,
    -20, -30, -30, -40, -40, -30, -30, -20,
    -10, -20, -20, -20, -20, -20, -20, -10,
    20, 20, 0, 0, 0, 0, 20, 20,
    20, 30, 10, 0, 0, 10, 30, 20,
]
PST = {
    chess.PAWN: PST_PAWN,
    chess.KNIGHT: PST_KNIGHT,
    chess.BISHOP: PST_BISHOP,
    chess.ROOK: PST_ROOK,
    chess.QUEEN: PST_QUEEN,
    chess.KING: PST_KING,
}


def ease_in_out_cubic(t: float) -> float:
    t = max(0.0, min(1.0, t))
    if t < 0.5:
        return 4 * t * t * t
    return 1 - (-2 * t + 2) ** 3 / 2


def evaluate_board(board: chess.Board) -> int:
    """Centipawn eval, positive = white better. Fast enough for depth-2."""
    if board.is_checkmate():
        return -10_000 if board.turn == chess.WHITE else 10_000
    if board.is_stalemate() or board.is_insufficient_material():
        return 0
    score = 0
    for sq in chess.SQUARES:
        piece = board.piece_at(sq)
        if piece is None:
            continue
        v = PIECE_VALUES[piece.piece_type] + PST[piece.piece_type][
            sq if piece.color == chess.WHITE else chess.square_mirror(sq)
        ]
        score += v if piece.color == chess.WHITE else -v
    return score


def search_best_move(board: chess.Board, depth: int = 2) -> chess.Move | None:
    """Tiny negamax with alpha-beta. Good enough for a casual opponent."""
    moves = list(board.legal_moves)
    if not moves:
        return None
    # Move ordering: captures first (MVV-LVA-ish) for better pruning.
    def order(m: chess.Move) -> int:
        cap = board.piece_at(m.to_square)
        return PIECE_VALUES.get(cap.piece_type, 0) if cap else 0

    moves.sort(key=order, reverse=True)

    def negamax(b: chess.Board, d: int, alpha: float, beta: float) -> float:
        if d == 0 or b.is_game_over():
            s = evaluate_board(b)
            return s if b.turn == chess.WHITE else -s
        best = -float("inf")
        for m in sorted(b.legal_moves, key=order, reverse=True):
            b.push(m)
            best = max(best, -negamax(b, d - 1, -beta, -alpha))
            b.pop()
            alpha = max(alpha, best)
            if alpha >= beta:
                break
        return best

    import random

    scored: list[tuple[float, chess.Move]] = []
    root_white = board.turn == chess.WHITE
    for m in moves:
        board.push(m)
        val = -negamax(board, depth - 1, -float("inf"), float("inf"))
        board.pop()
        if not root_white:
            val = -val
        scored.append((val, m))
    scored.sort(key=lambda x: x[0], reverse=root_white)
    # Pick randomly among near-best to feel human.
    top_score = scored[0][0]
    pool = [m for s, m in scored if abs(s - top_score) <= 25]
    return random.choice(pool)


# --------------------------------------------------------------------------
# Sound (synthesized, no assets needed)
# --------------------------------------------------------------------------

class SoundManager:
    def __init__(self) -> None:
        self.enabled = True
        self.ok = False
        try:
            pygame.mixer.init(frequency=22050, size=-16, channels=1)
            self.ok = True
        except Exception:
            self.ok = False

    def _tone(self, freq: float, ms: int, volume: float = 0.35, slide_to: float = 0) -> None:
        if not self.ok or not self.enabled:
            return
        try:
            rate = 22050
            n = int(rate * ms / 1000)
            buf = array.array("h")
            for i in range(n):
                t = i / rate
                f = freq + (slide_to - freq) * (i / max(1, n)) if slide_to else freq
                env = math.sin(math.pi * i / max(1, n))  # smooth in/out
                buf.append(int(32767 * volume * env * math.sin(2 * math.pi * f * t)))
            pygame.mixer.Sound(buffer=buf.tobytes()).play()
        except Exception:
            pass

    def move(self) -> None:
        self._tone(620, 70, 0.3, 440)

    def capture(self) -> None:
        self._tone(320, 110, 0.4, 160)

    def select(self) -> None:
        self._tone(880, 35, 0.15)

    def check(self) -> None:
        self._tone(980, 120, 0.35, 740)

    def castle(self) -> None:
        self._tone(500, 60, 0.3, 700)

    def promote(self) -> None:
        self._tone(700, 90, 0.35, 1050)

    def game_over(self) -> None:
        self._tone(392, 160, 0.35)
        pygame.time.delay(140)
        self._tone(330, 160, 0.35)
        pygame.time.delay(140)
        self._tone(262, 260, 0.35)


# --------------------------------------------------------------------------
# Piece rendering (unicode glyphs with outline + shadow, cached)
# --------------------------------------------------------------------------

class PieceRenderer:
    def __init__(self, square: int) -> None:
        self.square = square
        self.font: pygame.font.Font | None = None
        self.cache: dict[tuple[int, bool], pygame.Surface] = {}
        self._pick_font(int(square * 0.62))

    def _pick_font(self, size: int) -> None:
        # NOTE: order matters — "arialunicode" is the one that actually has
        # chess glyphs on macOS. Don't put segoe/symbola first: SysFont will
        # happily return a fallback font without chess coverage and every
        # piece renders as tofu boxes.
        for name in ("arialunicode", "arial", "menlo", "dejavusans", "freesans"):
            try:
                f = pygame.font.SysFont(name, size)
                # probe render
                if f.render("♚", True, (0, 0, 0)).get_width() > 4:
                    self.font = f
                    return
            except Exception:
                continue
        self.font = pygame.font.SysFont(None, size)

    def resize(self, square: int) -> None:
        if square != self.square:
            self.square = square
            self.cache.clear()
            self._pick_font(int(square * 0.62))

    def get(self, piece_type: int, color: bool) -> pygame.Surface:
        key = (piece_type, color)
        if key in self.cache:
            return self.cache[key]
        assert self.font is not None
        glyph = GLYPH[(piece_type, color)]
        # Soft, low-contrast palette: off-white pieces with warm grey edge,
        # dark slate pieces with light edge. Thin 1px outline keeps glyphs crisp.
        fill = (250, 250, 252) if color == chess.WHITE else (38, 38, 48)
        outline = (74, 74, 88) if color == chess.WHITE else (232, 232, 240)
        base = self.font.render(glyph, True, fill)
        edge = self.font.render(glyph, True, outline)
        w = base.get_width() + 4
        h = base.get_height() + 4
        surf = pygame.Surface((w, h), pygame.SRCALPHA)
        cx, cy = 2, 2
        for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1),
                       (-1, -1), (-1, 1), (1, -1), (1, 1)):
            surf.blit(edge, (cx + dx, cy + dy))
        surf.blit(base, (cx, cy))
        # subtle drop shadow
        shadow = pygame.Surface((w + 2, h + 4), pygame.SRCALPHA)
        shadow.blit(self.font.render(glyph, True, (0, 0, 0, 70)), (cx + 1, cy + 3))
        shadow.blit(surf, (0, 0))
        self.cache[key] = shadow
        return shadow


# --------------------------------------------------------------------------
# Animations
# --------------------------------------------------------------------------

@dataclass
class MoveAnim:
    piece_type: int
    color: bool
    from_px: tuple[float, float]
    to_px: tuple[float, float]
    t: float = 0.0
    duration: float = 0.22
    captured_surf: pygame.Surface | None = None
    captured_px: tuple[float, float] | None = None
    is_capture: bool = False


@dataclass
class Button:
    rect: pygame.Rect
    label: str
    action: str
    hover: bool = False


# --------------------------------------------------------------------------
# Game
# --------------------------------------------------------------------------

class ChessGame:
    def __init__(self) -> None:
        pygame.init()
        pygame.display.set_caption("Chesso ♞ — pygame + python-chess")
        self.screen = pygame.display.set_mode((WIN_W, WIN_H))
        self.clock = pygame.time.Clock()
        self.board = chess.Board()
        self.orientation_white = True  # True = white at bottom
        self.selected: chess.Square | None = None
        self.legal_for_selected: list[chess.Move] = []
        self.hover_sq: chess.Square | None = None
        self.dragging = False
        self.drag_pos: tuple[int, int] = (0, 0)
        self.drag_from: chess.Square | None = None
        self.anims: list[MoveAnim] = []
        self.last_move: chess.Move | None = None
        self.san_history: list[str] = []
        self.king_in_check_sq: chess.Square | None = None
        self.promotion_choices: list[chess.Move] = []
        self.promo_from: chess.Square | None = None
        self.promo_to: chess.Square | None = None
        self.game_over_text = ""
        self.game_over_sub = ""
        self.game_over_alpha = 0.0
        self.move_list_scroll = 0
        self.mode = "2P"  # 2P | AI_BLACK (you=white) | AI_WHITE (you=black)
        self.ai_thinking = False
        self.ai_thread: threading.Thread | None = None
        self.ai_move: chess.Move | None = None
        self.sound = SoundManager()
        self.renderer = PieceRenderer(BOARD_PX // 8)
        # --- Coach (ChessTempo-style grading) + puzzles ------------------
        self.coach = coach.EngineManager()
        self.coach_enabled = True
        self.coach_score = 0
        self.coach_streak = 0
        self.coach_best_streak = 0
        self.grades: list[tuple[int, coach.Grade]] = []  # (ply, grade): humans only
        self.last_grade: coach.Grade | None = None
        self.grade_thread: threading.Thread | None = None
        self.grading_busy = False
        # floating toast: (text, color, square_center, born_time)
        self.toast: tuple[str, tuple[int, int, int], tuple[float, float], float] | None = None
        # best-move arrow: (from_sq, to_sq, expires_at)
        self.best_arrow: tuple[chess.Square, chess.Square, float] | None = None
        # puzzle mode (Lichess-style lines: solution = [you, opp, you, ...])
        self.puzzle_mode = False
        self.puzzle_idx = -1
        self.puzzle: dict | None = None
        self.profile = profile_mod.load()
        self.puzzle_rating = self.profile.get("puzzle_rating", profile_mod.PUZZLE_START)
        self.subject_id: str = self.profile.get("subject_id", "unknown")
        self.session_id: str = uuid.uuid4().hex[:8]
        self.puzzle_status = ""  # solving | opp | solved | failed
        self.puzzle_ply = 0  # index into solution: even = your move
        self.pending_reply: tuple[chess.Move, float] | None = None
        self.daily_busy = False
        self.seen_puzzle_ids: set[str] = set()
        self.seen_puzzles: set[int] = set()  # legacy sample idxs
        self.puzzle_pool: list[dict] = coach.load_puzzle_file() or coach.sample_pool()
        # timed tiers + research timing
        self.puzzle_tier = "medium"
        self.puzzle_deadline = 0.0
        self.puzzle_attempts = 0
        self._pos_shown_at = time.time()
        self._puzzle_start_at = time.time()
        self._pending_meta: dict | None = None
        self._grade_meta: dict[int, dict] = {}  # ply -> timing, game moves
        self._spar_meta: dict | None = None
        self._hint_used = False
        self._hint_used_total = False
        self._seen_before = False
        self._second_chance_used = False
        self._fail_uci: str | None = None
        self._fail_at = 0.0
        self._solve_pending = False
        self._solve_at = 0.0
        self._first_label: str | None = None
        self._prev_grade: str | None = None
        self._prev_loss: int | None = None
        # gameplay AI strength + live sparring (Stockfish on the other side)
        self.ai_level = "auto"  # auto = adaptive ladder; or easy/medium/hard
        self.spar_mode = False
        self.spar_target = 0  # player moves to survive
        self.spar_moves = 0
        self.spar_pending_compute = False
        self._spar_judge_pending = False
        # rated play (game rating vs ladder AI)
        self.game_ai: dict | None = None  # {"name","rating"} snapshot at game start
        self.game_rated = False
        self._game_n = 0
        self._game_id = ""
        self._game_start_at = time.time()
        # screens: home | tiers | profile | play | puzzle
        self.screen_state = "home"
        self.study_screen = None
        self.study_options: dict = {}
        self.home_tiles: list[tuple[pygame.Rect, str]] = []
        self.tier_cards: list[tuple[pygame.Rect, str]] = []
        self.home_button = pygame.Rect(0, 0, 0, 0)
        self.back_button = pygame.Rect(0, 0, 0, 0)
        self.font_title = pygame.font.SysFont("helveticaneue", 30, bold=True)
        self.font_ui = pygame.font.SysFont("helveticaneue", 18)
        self.font_ui_b = pygame.font.SysFont("helveticaneue", 18, bold=True)
        self.font_small = pygame.font.SysFont("helveticaneue", 14)
        self.font_moves = pygame.font.SysFont("menlo", 15)
        self.font_glyph_small = pygame.font.SysFont("arialunicode", 20)
        self.start_time = time.time()
        self.buttons: list[Button] = []
        self._layout_buttons()
        self._refresh_check_state()

    # -- layout ---------------------------------------------------------
    def _layout_buttons(self) -> None:
        # Buttons sit inside the panel with padding so nothing overflows.
        # Panel spans BOARD_Y-8 .. BOARD_Y+BOARD_PX+8 (bottom = 728).
        panel_bottom = BOARD_Y + BOARD_PX + 8
        w, h, gap = (PANEL_W - 8) // 2, 36, 8
        x = PANEL_X
        y_bottom = panel_bottom - 30 - h  # 30px reserved for footer line
        y_top = y_bottom - gap - h
        self.buttons = [
            Button(pygame.Rect(x, y_top, w, h), "New (N)", "new"),
            Button(pygame.Rect(x + w + 8, y_top, w, h), "Undo (U)", "undo"),
            Button(pygame.Rect(x, y_bottom, w, h), "Flip (F)", "flip"),
            Button(pygame.Rect(x + w + 8, y_bottom, w, h), "Sound: On", "sound"),
        ]
        # AI mode button lives near top of panel; handled as separate rect.
        self.ai_button = pygame.Rect(PANEL_X, 148, PANEL_W, 36)
        self.ai_level_button = pygame.Rect(PANEL_X, 148, PANEL_W, 36)
        # Coach row: toggle / hint / puzzle (small buttons under move list)
        self.coach_button = pygame.Rect(PANEL_X + 14, 0, 0, 0)  # placed in _draw_panel
        self.hint_button = pygame.Rect(PANEL_X + 14, 0, 0, 0)
        self.puzzle_button = pygame.Rect(PANEL_X + 14, 0, 0, 0)
        self.spar_button = pygame.Rect(PANEL_X + 14, 0, 0, 0)

    # -- coordinates ----------------------------------------------------
    @property
    def sq_size(self) -> float:
        return BOARD_PX / 8

    def square_to_xy(self, sq: chess.Square) -> tuple[float, float]:
        file = chess.square_file(sq)
        rank = chess.square_rank(sq)
        if self.orientation_white:
            col, row = file, 7 - rank
        else:
            col, row = 7 - file, rank
        return BOARD_X + col * self.sq_size, BOARD_Y + row * self.sq_size

    def square_center(self, sq: chess.Square) -> tuple[float, float]:
        x, y = self.square_to_xy(sq)
        return x + self.sq_size / 2, y + self.sq_size / 2

    def pixel_to_square(self, px: int, py: int) -> chess.Square | None:
        if not (BOARD_X <= px < BOARD_X + BOARD_PX and BOARD_Y <= py < BOARD_Y + BOARD_PX):
            return None
        col = int((px - BOARD_X) // self.sq_size)
        row = int((py - BOARD_Y) // self.sq_size)
        if self.orientation_white:
            file, rank = col, 7 - row
        else:
            file, rank = 7 - col, row
        return chess.square(file, rank)

    # -- state ----------------------------------------------------------
    def _refresh_check_state(self) -> None:
        self.king_in_check_sq = None
        if self.board.is_check():
            color = self.board.turn
            for sq in chess.SQUARES:
                p = self.board.piece_at(sq)
                if p and p.piece_type == chess.KING and p.color == color:
                    self.king_in_check_sq = sq
                    break
        self._refresh_game_over()

    def _refresh_game_over(self) -> None:
        b = self.board
        if b.is_checkmate():
            winner = "Black" if b.turn == chess.WHITE else "White"
            self.game_over_text = f"Checkmate · {winner} wins"
            self.game_over_sub = "Press N for a new game · U to undo"
        elif b.is_stalemate():
            self.game_over_text = "Draw · stalemate"
            self.game_over_sub = "Press N for a new game · U to undo"
        elif b.is_insufficient_material():
            self.game_over_text = "Draw · insufficient material"
            self.game_over_sub = "Press N for a new game"
        elif b.is_seventyfive_moves() or b.is_fivefold_repetition():
            self.game_over_text = "Draw · repetition / 75-move rule"
            self.game_over_sub = "Press N for a new game"
        else:
            self.game_over_text = ""
            self.game_over_sub = ""

    def is_ai_turn(self) -> bool:
        if self.puzzle_mode or self.spar_mode:
            return False
        if self.game_over_text or self.anims or self.promotion_choices:
            return False
        if self.mode == "AI_BLACK":
            return self.board.turn == chess.BLACK
        if self.mode == "AI_WHITE":
            return self.board.turn == chess.WHITE
        return False

    def human_can_move(self) -> bool:
        if self.puzzle_mode and self.puzzle_status in ("solved", "failed", "failed_pending"):
            return False
        if self.spar_mode and self.puzzle_status in ("solved", "failed"):
            return False
        if self.pending_reply is not None or self.spar_pending_compute:
            return False
        return not self.anims and not self.promotion_choices and not self.ai_thinking and not self.game_over_text

    # -- moves ----------------------------------------------------------
    def legal_moves_from(self, sq: chess.Square) -> list[chess.Move]:
        return [m for m in self.board.legal_moves if m.from_square == sq]

    def select(self, sq: chess.Square) -> None:
        piece = self.board.piece_at(sq)
        if piece and piece.color == self.board.turn:
            if self.human_can_move() and not self._ai_blocks_human():
                self.selected = sq
                self.legal_for_selected = self.legal_moves_from(sq)
                self.sound.select()
        elif self.selected is not None:
            self.attempt_move(self.selected, sq)

    def _ai_blocks_human(self) -> bool:
        if self.mode == "AI_BLACK" and self.board.turn == chess.BLACK:
            return True
        if self.mode == "AI_WHITE" and self.board.turn == chess.WHITE:
            return True
        return False

    def attempt_move(self, frm: chess.Square, to: chess.Square) -> bool:
        candidates = [m for m in self.board.legal_moves if m.from_square == frm and m.to_square == to]
        if not candidates:
            # reselect if own piece clicked
            p = self.board.piece_at(to)
            if p and p.color == self.board.turn and not self._ai_blocks_human():
                self.selected = to
                self.legal_for_selected = self.legal_moves_from(to)
                self.sound.select()
            else:
                self.selected = None
                self.legal_for_selected = []
            return False
        if len(candidates) > 1 and any(m.promotion for m in candidates):
            # need promotion choice
            self.promotion_choices = candidates
            self.promo_from, self.promo_to = frm, to
            return True
        self.push_move(candidates[0])
        return True

    def push_move(self, move: chess.Move, coach_grade: bool = True) -> None:
        piece = self.board.piece_at(move.from_square)
        assert piece is not None
        before_board = self.board.copy()
        # Opponent auto-replies bypass checks+grading (puzzles + sparring).
        is_opponent_reply = (self.puzzle_mode or self.spar_mode) and not coach_grade
        captured = self.board.piece_at(move.to_square)
        is_en_passant = self.board.is_en_passant(move)
        is_castle = self.board.is_castling(move)
        san = self.board.san(move)
        cap_piece = captured
        if is_en_passant:
            cap_sq = move.to_square + (-8 if self.board.turn == chess.WHITE else 8)
            cap_piece = self.board.piece_at(cap_sq)

        fx, fy = self.square_center(move.from_square)
        tx, ty = self.square_center(move.to_square)
        anim = MoveAnim(
            piece_type=piece.piece_type if move.promotion is None else move.promotion,
            color=piece.color,
            from_px=(fx, fy),
            to_px=(tx, ty),
            duration=0.24 if (captured or is_castle) else 0.19,
            is_capture=bool(captured or is_en_passant),
        )
        if cap_piece is not None:
            anim.captured_surf = self.renderer.get(cap_piece.piece_type, cap_piece.color)
            anim.captured_px = self.square_center(
                move.to_square if not is_en_passant else move.to_square + (-8 if piece.color == chess.WHITE else 8)
            )
        self.anims.append(anim)

        # castling rook slide
        if is_castle:
            if chess.square_file(move.to_square) == 6:  # kingside
                rf, rt = move.from_square + 3, move.from_square + 1
            else:  # queenside
                rf, rt = move.from_square - 4, move.from_square - 1
            rook = self.board.piece_at(rf)
            if rook:
                rfx, rfy = self.square_center(rf)
                rtx, rty = self.square_center(rt)
                self.anims.append(
                    MoveAnim(piece_type=rook.piece_type, color=rook.color,
                             from_px=(rfx, rfy), to_px=(rtx, rty), duration=0.24)
                )

        self.board.push(move)
        self.san_history.append(san)
        self.last_move = move
        self.selected = None
        self.legal_for_selected = []
        self.promotion_choices = []
        self.promo_from = self.promo_to = None
        self._refresh_check_state()

        # sounds
        if self.board.is_checkmate():
            self.sound.game_over()
        elif self.board.is_check():
            self.sound.check()
        elif move.promotion:
            self.sound.promote()
        elif is_castle:
            self.sound.castle()
        elif captured or is_en_passant:
            self.sound.capture()
        else:
            self.sound.move()

        # --- Coach grading: HUMAN moves only (never the AI's) ---------------
        if self._should_grade(before_board.turn, coach_grade):
            self._request_grade(before_board, move)

        # --- Rated-game snapshot (adaptive AI rung, once per game) ---------
        if (self.game_ai is None and self.mode in ("AI_BLACK", "AI_WHITE")
                and not self.puzzle_mode and not self.spar_mode
                and not self.game_over_text):
            rung = self.matched_rung()
            self._game_n += 1
            self._game_id = f"game-{self.session_id}-{self._game_n}"
            self._game_start_at = time.time()
            self.game_ai = {"name": rung["name"], "rating": rung["rating"]}
            self.game_rated = False
        if not self.puzzle_mode and not self.spar_mode:
            # deliberation clock for game moves (captured now; the grade
            # lands later, after the AI has already replied)
            now = time.time()
            self._grade_meta[len(self.board.move_stack)] = {
                "ms_delib": int((now - self._pos_shown_at) * 1000),
                "ms_total": int((now - self._game_start_at) * 1000),
            }
            self._pos_shown_at = now

        # --- Puzzle exact-match flow (Lichess-style lines) -----------------
        if self.puzzle_mode and self.puzzle is not None and not is_opponent_reply:
            self._puzzle_after_player_move(before_board, move)
        elif is_opponent_reply and self.puzzle_mode:
            # reply consumed one ply; keep solving unless line is over
            sol = (self.puzzle.get("solution") or []) if self.puzzle else []
            if self.puzzle_status == "solving" and self.puzzle_ply >= len(sol):
                self._puzzle_solved()
            self._pos_shown_at = time.time()  # fresh position for timing

        # --- Sparring flow (live Stockfish opponent) -----------------------
        if self.spar_mode and coach_grade and self.puzzle is not None:
            self._spar_after_player_move(move)
        if self.spar_mode and is_opponent_reply and self.puzzle_status == "solving":
            if self.board.is_checkmate():
                self._spar_failed("Mated by spar partner")
            elif self.board.is_game_over():
                self._spar_failed("No win — draw")

    # -- coach ----------------------------------------------------------
    def _mover_is_human(self, color: bool) -> bool:
        """AI-held sides never earn the user points."""
        if self.mode == "AI_BLACK" and color == chess.BLACK:
            return False
        if self.mode == "AI_WHITE" and color == chess.WHITE:
            return False
        return True

    def _should_grade(self, mover_color: bool, coach_grade: bool) -> bool:
        if not self.coach_enabled or not coach_grade:
            return False
        if self.puzzle_mode or self.spar_mode:
            return True  # only the player's moves reach here (replies skip)
        return self._mover_is_human(mover_color)

    def _request_grade(self, before: chess.Board, played: chess.Move) -> None:
        if self.grading_busy:
            return
        self.grading_busy = True
        snapshot = before.copy()
        mv = played
        ply = len(self.board.move_stack)  # grade sticks to this position

        def worker() -> None:
            try:
                g = self.coach.grade(snapshot, mv, time_s=0.3, depth=14)
            except Exception:
                g = None
            self._apply_grade(g, mv, ply)

        threading.Thread(target=worker, daemon=True).start()

    def _apply_grade(self, g: coach.Grade | None, played: chess.Move, ply: int = -1) -> None:
        self.grading_busy = False
        if g is None:
            return
        if ply < 0:
            ply = len(self.board.move_stack)
        self.grades.append((ply, g))
        self.last_grade = g
        # score + streak (good moves build streak bonus)
        if g.points > 0:
            self.coach_streak += 1
            bonus = min(10, (self.coach_streak - 1) * 2)
            self.coach_score += g.points + bonus
            self.coach_best_streak = max(self.coach_best_streak, self.coach_streak)
        else:
            self.coach_streak = 0
            self.coach_score += g.points  # negative
        # toast over destination square
        try:
            cx, cy = self.square_center(played.to_square)
        except Exception:
            cx, cy = BOARD_X + BOARD_PX / 2, BOARD_Y + BOARD_PX / 2
        color = coach.LABEL_COLORS.get(g.label, (235, 235, 245))
        sign = f"+{g.points}" if g.points >= 0 else f"{g.points}"
        self.toast = (f"{g.label} {sign}", color, (cx, cy), time.time())
        # best-move arrow when user missed it (4s)
        try:
            best_mv = chess.Move.from_uci(g.best_uci)
            if best_mv != played and g.label in ("Inaccuracy", "Mistake", "Blunder"):
                self.best_arrow = (best_mv.from_square, best_mv.to_square,
                                   time.time() + 4.0)
            elif self.puzzle_mode and self.puzzle_status == "failed":
                self.best_arrow = (best_mv.from_square, best_mv.to_square,
                                   time.time() + 8.0)
        except Exception:
            pass
        # puzzle rating update — only for engine-judged (solution=None)
        # fallback puzzles. Solution puzzles are rated synchronously by
        # exact match in _puzzle_after_player_move (status already final).
        if (self.puzzle_mode and self.puzzle is not None
                and self.puzzle_status == "solving"
                and not self.puzzle.get("solution")):
            self._pending_meta = self._pending_meta or {
                "uci": played.uci(), "attempt_no": self.puzzle_attempts + 1,
                "move_no_in_line": 1,
                "ms_delib": int((time.time() - self._pos_shown_at) * 1000),
                "ms_total": int((time.time() - self._puzzle_start_at) * 1000),
                "clock_left_ms": int(max(0.0, self.puzzle_deadline - time.time()) * 1000),
                "hint_used": self._hint_used,
            }
            self.puzzle_attempts += 1
            self._hint_used = False
            solved = g.cp_loss <= 30
            if solved:
                self.puzzle_status = "solved"
                self._solve_pending = True
                self._solve_at = time.time()
                self._first_label = g.label
                self.sound.promote()
                self.toast = ("Solved!", (110, 200, 130),
                              (BOARD_X + BOARD_PX / 2, BOARD_Y + 70), time.time())
            else:
                self._fail_uci = g.best_uci
                self._fail_at = time.time()
                self.puzzle_status = "failed_pending"
                self.toast = ("Not it…", (240, 200, 90),
                              (BOARD_X + BOARD_PX / 2, BOARD_Y + 70), time.time())
        # research: log every graded player attempt (puzzle / spar / game)
        self._log_graded_attempt(g, played, ply)
        # partial credit: wrong-but-decent first try → +3 + second chance
        if (self.puzzle_mode and self.puzzle_status == "failed_pending"
                and not self._second_chance_used and self._pending_meta
                and self._pending_meta.get("attempt_no", 2) == 1
                and g.label in ("Best", "Excellent", "Good")
                and g.cp_loss <= profile_mod.VALID_LOSS_MAX):
            self._second_chance_used = True
            self.puzzle_status = "solving"
            self.best_arrow = None  # keep the challenge: no free answer
            self.coach_score += profile_mod.VALID_POINTS
            self.profile["points_total"] = self.profile.get("points_total", 0) + profile_mod.VALID_POINTS
            profile_mod.save(self.profile)
            self._pending_meta["points"] = profile_mod.VALID_POINTS
            self.toast = (f"Valid +{profile_mod.VALID_POINTS} — find the best!",
                          (240, 200, 90), (BOARD_X + BOARD_PX / 2, BOARD_Y + 70),
                          time.time())
            self.sound.select()
        elif self.puzzle_mode and self.puzzle_status == "failed_pending":
            # grade confirms the miss (or second chance already used) → fail
            meta_uci = self._fail_uci or played.uci()
            try:
                before = self._reconstruct_before(played)
                self._puzzle_failed(meta_uci, before)
            except Exception:
                if self.puzzle is not None:
                    self._puzzle_failed(meta_uci, self.board)
        # first-attempt label powers the +10% Best bonus at solve time
        if self._pending_meta and self._pending_meta.get("attempt_no") == 1:
            self._first_label = g.label
        self._prev_grade, self._prev_loss = g.label, g.cp_loss
        self._pending_meta = None
        # sparring judgement — survive without Mistake/Blunder
        if (self.spar_mode and self._spar_judge_pending
                and self.puzzle_status == "solving"):
            self._spar_judge_pending = False
            if g.label in ("Mistake", "Blunder"):
                self._spar_failed(f"{g.label} {g.points:+d}")
            elif self.spar_moves < self.spar_target:
                self._request_spar_reply()

    def _reconstruct_before(self, played: chess.Move) -> chess.Board:
        """Board before the last push (for SAN of the expected move)."""
        b = self.board.copy()
        try:
            b.pop()
        except Exception:
            pass
        return b

    def _puzzle_failed_engine(self, timeout: bool = False) -> None:
        """Terminal fail for engine-judged puzzles (no reference line)."""
        self.puzzle_status = "failed"
        self.pending_reply = None
        assert self.puzzle is not None
        tier = self.puzzle_tier
        now = time.time()
        pr_before = self.profile.get("puzzle_rating", profile_mod.PUZZLE_START)
        delta = profile_mod.rate_puzzle(self.profile, self.puzzle["rating"], False, tier=tier)
        self.puzzle_rating = self.profile["puzzle_rating"]
        self.seen_puzzle_ids.add(str(self.puzzle.get("id")))
        self.coach_streak = 0
        reason = "Time!" if timeout else "Miss"
        self.toast = (f"{reason} · Elo {self.puzzle_rating}", (235, 90, 90),
                      (BOARD_X + BOARD_PX / 2, BOARD_Y + 70), now)
        profile_mod.log_attempt({
            "v": 1, "kind": "puzzle_result", "subject": self.subject_id,
            "session": self.session_id, "mode": "puzzle",
            "calibration": profile_mod.calibration_puzzle(self.profile),
            "puzzle_id": str(self.puzzle.get("id")), "puzzle_rating": self.puzzle["rating"],
            "tier": tier, "solution_len": 0, "seen_before": self._seen_before,
            "solved": False, "timeout": timeout, "terminal": True, "points": 0,
            "attempts": self.puzzle_attempts,
            "ms_total": int((now - self._puzzle_start_at) * 1000),
            "pr_before": pr_before, "pr_after": self.puzzle_rating, "pr_delta": delta,
        })
        self.sound.capture()

    def _log_graded_attempt(self, g: coach.Grade, played: chess.Move, ply: int = -1) -> None:
        """One detailed research row per graded player move (never raises)."""
        try:
            now = time.time()
            meta = self._pending_meta or {}
            if self.puzzle_mode and self.puzzle is not None:
                profile_mod.log_attempt({
                    "v": 1, "kind": "attempt", "subject": self.subject_id,
                    "session": self.session_id, "mode": "puzzle",
                    "calibration": profile_mod.calibration_puzzle(self.profile),
                    "puzzle_id": str(self.puzzle.get("id")),
                    "puzzle_rating": self.puzzle["rating"], "tier": self.puzzle_tier,
                    "solution_len": len(self.puzzle.get("solution") or []),
                    "seen_before": self._seen_before,
                    "hint_used": meta.get("hint_used", False),
                    "attempt_no": meta.get("attempt_no", self.puzzle_attempts),
                    "move_no_in_line": meta.get("move_no_in_line", 0),
                    "uci": played.uci(), "san": g.played_san, "grade": g.label,
                    "cp_loss": g.cp_loss, "eval_played": g.played_eval,
                    "eval_best": g.best_eval,
                    "ms_delib": meta.get("ms_delib"), "ms_total": meta.get("ms_total"),
                    "clock_left_ms": meta.get("clock_left_ms"),
                    "clock_total_ms": profile_mod.TIERS[self.puzzle_tier]["time"] * 1000,
                    "prev_grade": self._prev_grade, "prev_loss": self._prev_loss,
                    "points": meta.get("points", 0),
                    "user_pr_before": self.profile.get("puzzle_rating"),
                })
            elif self.spar_mode and self.puzzle is not None:
                smeta = self._spar_meta or {}
                profile_mod.log_attempt({
                    "v": 1, "kind": "attempt", "subject": self.subject_id,
                    "session": self.session_id, "mode": "spar",
                    "calibration": profile_mod.calibration_puzzle(self.profile),
                    "puzzle_id": str(self.puzzle.get("id")),
                    "puzzle_rating": self.puzzle["rating"],
                    "tier": profile_mod.tier_of(int(self.puzzle.get("rating", 1200))),
                    "seen_before": self._seen_before,
                    "hint_used": self._hint_used,
                    "move_no_in_line": self.spar_moves,
                    "uci": played.uci(), "san": g.played_san, "grade": g.label,
                    "cp_loss": g.cp_loss, "eval_played": g.played_eval,
                    "eval_best": g.best_eval,
                    "ms_delib": smeta.get("ms_delib"),
                    "ms_total": smeta.get("ms_total"),
                    "prev_grade": self._prev_grade, "prev_loss": self._prev_loss,
                    "user_pr_before": self.profile.get("puzzle_rating"),
                })
                self._hint_used = False
                self._spar_meta = None
            elif self.game_ai is not None and not self.puzzle_mode and not self.spar_mode:
                gmeta = self._grade_meta.pop(ply, {})
                profile_mod.log_attempt({
                    "v": 1, "kind": "game_move", "subject": self.subject_id,
                    "session": self.session_id, "mode": "game",
                    "calibration": profile_mod.calibration_game(self.profile),
                    "game_id": self._game_id, "ai_name": self.game_ai.get("name"),
                    "ai_rating": self.game_ai.get("rating"), "tier": "game",
                    "uci": played.uci(), "san": g.played_san, "grade": g.label,
                    "cp_loss": g.cp_loss, "eval_played": g.played_eval,
                    "eval_best": g.best_eval,
                    "ms_delib": gmeta.get("ms_delib"),
                    "ms_total": gmeta.get("ms_total"),
                    "prev_grade": self._prev_grade, "prev_loss": self._prev_loss,
                    "user_pr_before": self.profile.get("game_rating"),
                })
        except Exception:
            pass

    def show_hint(self) -> None:
        """Hint (H): best arrow for 3s, costs 5 pts. In puzzles: the solution."""
        if self.game_over_text:
            return
        if self.puzzle_mode and self.puzzle is not None and self.puzzle_status == "solving":
            sol = self.puzzle.get("solution") or []
            if self.puzzle_ply < len(sol):
                try:
                    mv = chess.Move.from_uci(sol[self.puzzle_ply])
                except Exception:
                    return
                self.best_arrow = (mv.from_square, mv.to_square, time.time() + 3.0)
                self.coach_score -= 5
                self._hint_used = True  # logged; voids the +10% bonus
                self._hint_used_total = True
                cx, cy = self.square_center(mv.to_square)
                self.toast = ("Hint (-5)", (129, 182, 255), (cx, cy), time.time())
                self.sound.select()
                return
        if self.grading_busy:
            return
        try:
            best, _, _, _ = self.coach.best_in_position(self.board, time_s=0.25)
        except Exception:
            return
        if best is None:
            return
        self.best_arrow = (best.from_square, best.to_square, time.time() + 3.0)
        self.coach_score -= 5
        if self.spar_mode:
            self._hint_used = True
        try:
            san = self.board.san(best)
        except Exception:
            san = best.uci()
        cx, cy = self.square_center(best.to_square)
        self.toast = (f"Hint: {san}  (-5)", (129, 182, 255), (cx, cy), time.time())
        self.sound.select()

    # -- puzzles (Lichess-style multi-move lines) --------------------------
    def _puzzle_after_player_move(self, before: chess.Board, played: chess.Move) -> None:
        """Exact-match judging for solution puzzles (Lichess/ChessTempo)."""
        assert self.puzzle is not None
        sol = self.puzzle.get("solution")
        if not sol or self.puzzle_status != "solving":
            return  # engine-judged fallback handled via grades
        if self.puzzle_ply >= len(sol):
            return
        now = time.time()
        self.puzzle_attempts += 1
        self._pending_meta = {
            "uci": played.uci(), "attempt_no": self.puzzle_attempts,
            "move_no_in_line": self.puzzle_ply + 1,
            "ms_delib": int((now - self._pos_shown_at) * 1000),
            "ms_total": int((now - self._puzzle_start_at) * 1000),
            "clock_left_ms": int(max(0.0, self.puzzle_deadline - now) * 1000),
            "hint_used": self._hint_used,
        }
        self._hint_used = False
        expected_uci = sol[self.puzzle_ply]
        mate_alt = (
            "mateIn1" in (self.puzzle.get("themes") or [])
            and self.board.is_checkmate()
        )
        if played.uci() == expected_uci or mate_alt:
            self.puzzle_ply += 1
            if self.puzzle_ply >= len(sol):
                self._puzzle_solved()
            else:
                # schedule opponent auto-reply (odd ply) with a beat
                try:
                    reply = chess.Move.from_uci(sol[self.puzzle_ply])
                    assert reply in self.board.legal_moves
                    self.puzzle_ply += 1
                    self.pending_reply = (reply, time.time() + 0.8)
                    self.puzzle_status = "solving"  # still solving; input locked
                except Exception:
                    self._puzzle_solved()
        else:
            # don't finalize yet: the grade (~0.5s) decides fail vs +3 second chance
            self.puzzle_status = "failed_pending"
            self._fail_uci = expected_uci
            self._fail_at = now
            try:
                exp = chess.Move.from_uci(expected_uci)
                self.best_arrow = (exp.from_square, exp.to_square, time.time() + 8.0)
            except Exception:
                pass
            self.toast = ("Not it…", (240, 200, 90),
                          (BOARD_X + BOARD_PX / 2, BOARD_Y + 70), now)

    def _puzzle_solved(self) -> None:
        self.puzzle_status = "solved"
        self.pending_reply = None
        self._solve_pending = True
        self._solve_at = time.time()
        self.sound.promote()
        self.toast = ("Solved!", (110, 200, 130),
                      (BOARD_X + BOARD_PX / 2, BOARD_Y + 70), time.time())

    def _finalize_puzzle_solve(self) -> None:
        """Rating + points + terminal log once the first grade lands (bonus needs it)."""
        self._solve_pending = False
        if self.puzzle is None:
            return
        assert self.puzzle is not None
        tier = self.puzzle_tier
        now = time.time()
        seconds_left = max(0.0, self.puzzle_deadline - now)
        first_try_best = (self.puzzle_attempts <= 1 and self._first_label == "Best"
                          and not self._second_chance_used and not self._hint_used_total)
        points = profile_mod.solve_points(tier, seconds_left, first_try_best)
        pr_before = self.profile.get("puzzle_rating", profile_mod.PUZZLE_START)
        delta = profile_mod.rate_puzzle(self.profile, self.puzzle["rating"], True, tier=tier)
        self.puzzle_rating = self.profile["puzzle_rating"]
        self.profile["points_total"] = self.profile.get("points_total", 0) + points
        profile_mod.save(self.profile)
        self.seen_puzzle_ids.add(str(self.puzzle.get("id")))
        self.coach_score += points
        self.coach_streak += 1
        self.coach_best_streak = max(self.coach_best_streak, self.coach_streak)
        self.toast = (f"Solved! +{points} · Elo {self.puzzle_rating}", (110, 200, 130),
                      (BOARD_X + BOARD_PX / 2, BOARD_Y + 70), now)
        profile_mod.log_attempt({
            "v": 1, "kind": "puzzle_result", "subject": self.subject_id,
            "session": self.session_id, "mode": "puzzle",
            "calibration": profile_mod.calibration_puzzle(self.profile),
            "puzzle_id": str(self.puzzle.get("id")), "puzzle_rating": self.puzzle["rating"],
            "tier": tier, "solution_len": len(self.puzzle.get("solution") or []),
            "seen_before": self._seen_before, "solved": True, "timeout": False,
            "terminal": True, "points": points, "first_try_best": first_try_best,
            "attempts": self.puzzle_attempts,
            "ms_total": int((now - self._puzzle_start_at) * 1000),
            "pr_before": pr_before, "pr_after": self.puzzle_rating, "pr_delta": delta,
        })

    def _puzzle_failed(self, expected_uci: str, before: chess.Board,
                       reason: str = "Miss", timeout: bool = False) -> None:
        self.puzzle_status = "failed"
        self.pending_reply = None
        assert self.puzzle is not None
        tier = self.puzzle_tier
        now = time.time()
        pr_before = self.profile.get("puzzle_rating", profile_mod.PUZZLE_START)
        delta = profile_mod.rate_puzzle(self.profile, self.puzzle["rating"], False, tier=tier)
        self.puzzle_rating = self.profile["puzzle_rating"]
        self.seen_puzzle_ids.add(str(self.puzzle.get("id")))
        self.coach_streak = 0
        try:
            exp = chess.Move.from_uci(expected_uci)
            self.best_arrow = (exp.from_square, exp.to_square, time.time() + 8.0)
            try:
                san = before.san(exp)
            except Exception:
                san = expected_uci
            self.toast = (f"{reason} — was {san} · Elo {self.puzzle_rating}",
                          (235, 90, 90), (BOARD_X + BOARD_PX / 2, BOARD_Y + 70), now)
        except Exception:
            pass
        profile_mod.log_attempt({
            "v": 1, "kind": "puzzle_result", "subject": self.subject_id,
            "session": self.session_id, "mode": "puzzle",
            "calibration": profile_mod.calibration_puzzle(self.profile),
            "puzzle_id": str(self.puzzle.get("id")), "puzzle_rating": self.puzzle["rating"],
            "tier": tier, "solution_len": len(self.puzzle.get("solution") or []),
            "seen_before": self._seen_before, "solved": False, "timeout": timeout,
            "terminal": True, "points": 0, "attempts": self.puzzle_attempts,
            "ms_total": int((now - self._puzzle_start_at) * 1000),
            "pr_before": pr_before, "pr_after": self.puzzle_rating, "pr_delta": delta,
        })
        self.sound.capture()

    def _puzzle_timeout(self) -> None:
        if not (self.puzzle_mode and self.puzzle_status == "solving"):
            return
        sol = (self.puzzle or {}).get("solution") or []
        exp_uci = sol[self.puzzle_ply] if self.puzzle_ply < len(sol) else None
        if exp_uci is None:  # engine-judged: fail without a reference move
            self._puzzle_failed_engine(timeout=True)
            return
        self._puzzle_failed(exp_uci, self.board, reason="Time!", timeout=True)

    def fire_pending_reply(self) -> None:
        if self.pending_reply is None or self.anims:
            return
        reply, due = self.pending_reply
        if time.time() < due:
            return
        self.pending_reply = None
        if self.puzzle_status == "solving" and reply in self.board.legal_moves:
            self.push_move(reply, coach_grade=False)
            self._pos_shown_at = time.time()

    # -- sparring (live Stockfish on the other side) ------------------------
    def enter_spar(self) -> None:
        self.puzzle_mode = False
        self.spar_mode = True
        self._next_spar()

    def exit_spar(self) -> None:
        self.spar_mode = False
        self.spar_pending_compute = False
        self._spar_judge_pending = False
        self.puzzle = None
        self.puzzle_status = ""
        self.pending_reply = None
        self.best_arrow = None
        self.new_game()

    def _next_spar(self) -> None:
        if not self.puzzle_pool:
            self.puzzle_pool = coach.sample_pool()
        try:
            _, p = coach.pick_from_pool(self.puzzle_pool, self.puzzle_rating,
                                        self.seen_puzzle_ids or None)
        except Exception:
            p = self.puzzle_pool[0]
        if (len(self.seen_puzzle_ids) >= len(self.puzzle_pool)
                and len(self.puzzle_pool) > 1):
            self.seen_puzzle_ids.clear()
            _, p = coach.pick_from_pool(self.puzzle_pool, self.puzzle_rating, None)
        sol = p.get("solution") or []
        self.spar_target = max(2, (len(sol) + 1) // 2) if sol else 4
        self.spar_moves = 0
        self.spar_pending_compute = False
        self._spar_judge_pending = False
        self._load_puzzle(p)
        themes = " ".join((p.get("themes") or ["tactic"])[:2])
        self.toast = (f"SPAR {themes} · survive {self.spar_target} · {p.get('rating', '?')}",
                      (129, 182, 255), (BOARD_X + BOARD_PX / 2, BOARD_Y + 60),
                      time.time())

    def _spar_after_player_move(self, played: chess.Move) -> None:
        if self.puzzle_status != "solving":
            return
        now = time.time()
        self._spar_meta = {
            "ms_delib": int((now - self._pos_shown_at) * 1000),
            "ms_total": int((now - self._puzzle_start_at) * 1000),
        }
        if self.board.is_checkmate():
            self._spar_solved("Mate! +15")
            return
        if self.board.is_game_over():
            self._spar_failed("No win — draw")
            return
        self.spar_moves += 1
        if self.spar_moves >= self.spar_target:
            # survived the line; grade still lands for toast/score
            self._spar_solved(f"Survived {self.spar_target}! +15")
            return
        if self.grading_busy and self.coach_enabled:
            self._spar_judge_pending = True  # verdict lands with the grade
        else:
            self._request_spar_reply()  # no judge available; keep flowing

    def _request_spar_reply(self) -> None:
        if (not self.spar_mode or self.puzzle_status != "solving"
                or self.spar_pending_compute or self.pending_reply is not None):
            return
        self.spar_pending_compute = True
        snapshot = self.board.copy()

        def worker() -> None:
            try:
                mv = self.coach.choose_move(snapshot, "medium")
            except Exception:
                mv = None
            if (self.spar_mode and self.puzzle_status == "solving"
                    and mv is not None and mv in self.board.legal_moves):
                self.pending_reply = (mv, time.time() + 0.5)
            self.spar_pending_compute = False

        threading.Thread(target=worker, daemon=True).start()

    def _spar_solved(self, msg: str) -> None:
        self.puzzle_status = "solved"
        self.pending_reply = None
        self.spar_pending_compute = False
        self._spar_judge_pending = False
        now = time.time()
        pr = (self.puzzle or {}).get("rating", 1200)
        pr_before = self.profile.get("puzzle_rating", profile_mod.PUZZLE_START)
        delta = profile_mod.rate_puzzle(self.profile, pr, True)
        self.puzzle_rating = self.profile["puzzle_rating"]
        if self.puzzle:
            self.seen_puzzle_ids.add(str(self.puzzle.get("id")))
        self.coach_score += 15
        self.coach_streak += 1
        self.coach_best_streak = max(self.coach_best_streak, self.coach_streak)
        self.toast = (f"{msg} · Elo {self.puzzle_rating}", (110, 200, 130),
                      (BOARD_X + BOARD_PX / 2, BOARD_Y + 70), now)
        profile_mod.log_attempt({
            "v": 1, "kind": "spar_result", "subject": self.subject_id,
            "session": self.session_id, "mode": "spar",
            "calibration": profile_mod.calibration_puzzle(self.profile),
            "puzzle_id": str((self.puzzle or {}).get("id")),
            "puzzle_rating": pr, "tier": profile_mod.tier_of(int(pr)),
            "seen_before": self._seen_before, "solved": True, "timeout": False,
            "terminal": True, "points": 15, "moves": self.spar_moves,
            "ms_total": int((now - self._puzzle_start_at) * 1000),
            "pr_before": pr_before, "pr_after": self.puzzle_rating, "pr_delta": delta,
        })
        self.sound.promote()

    def _spar_failed(self, msg: str) -> None:
        self.puzzle_status = "failed"
        self.pending_reply = None
        self.spar_pending_compute = False
        self._spar_judge_pending = False
        now = time.time()
        pr = (self.puzzle or {}).get("rating", 1200)
        pr_before = self.profile.get("puzzle_rating", profile_mod.PUZZLE_START)
        delta = profile_mod.rate_puzzle(self.profile, pr, False)
        self.puzzle_rating = self.profile["puzzle_rating"]
        if self.puzzle:
            self.seen_puzzle_ids.add(str(self.puzzle.get("id")))
        self.coach_streak = 0
        if self.board.is_checkmate() and self.board.turn != chess.WHITE:
            pass  # player got mated; board says it all
        self.toast = (f"{msg} · Elo {self.puzzle_rating}", (235, 90, 90),
                      (BOARD_X + BOARD_PX / 2, BOARD_Y + 70), now)
        profile_mod.log_attempt({
            "v": 1, "kind": "spar_result", "subject": self.subject_id,
            "session": self.session_id, "mode": "spar",
            "calibration": profile_mod.calibration_puzzle(self.profile),
            "puzzle_id": str((self.puzzle or {}).get("id")),
            "puzzle_rating": pr, "tier": profile_mod.tier_of(int(pr)),
            "seen_before": self._seen_before, "solved": False, "timeout": False,
            "terminal": True, "points": 0, "moves": self.spar_moves,
            "ms_total": int((now - self._puzzle_start_at) * 1000),
            "pr_before": pr_before, "pr_after": self.puzzle_rating, "pr_delta": delta,
        })
        self.sound.capture()

    def enter_puzzle(self) -> None:
        self.puzzle_mode = True
        self._next_puzzle()

    def fetch_daily_puzzle(self) -> None:
        if self.daily_busy:
            return
        self.daily_busy = True

        def worker() -> None:
            try:
                p = coach.fetch_daily()
            except Exception:
                p = None
            self.daily_busy = False
            if p is None:
                return
            if not any(x.get("id") == p["id"] for x in self.puzzle_pool):
                self.puzzle_pool.append(p)
                coach.save_puzzle_file(self.puzzle_pool)
            self.puzzle_mode = True
            self._load_puzzle(p)

        threading.Thread(target=worker, daemon=True).start()

    def exit_puzzle(self) -> None:
        self.puzzle_mode = False
        self.puzzle = None
        self.puzzle_status = ""
        self.puzzle_ply = 0
        self.pending_reply = None
        self.best_arrow = None
        self._solve_pending = False
        self._pending_meta = None
        self.new_game()

    def _load_puzzle(self, p: dict, tier: str | None = None) -> None:
        self.puzzle = p
        self.puzzle_status = "solving"
        self.puzzle_ply = 0
        self.pending_reply = None
        now = time.time()
        self.puzzle_tier = tier or profile_mod.tier_of(int(p.get("rating", 1200)))
        self.puzzle_deadline = now + profile_mod.TIERS[self.puzzle_tier]["time"]
        self.puzzle_attempts = 0
        self._pos_shown_at = now
        self._puzzle_start_at = now
        self._pending_meta = None
        self._hint_used = False
        self._hint_used_total = False
        self._seen_before = str(p.get("id")) in self.seen_puzzle_ids
        self._second_chance_used = False
        self._fail_uci = None
        self._solve_pending = False
        self._first_label = None
        self._prev_grade = None
        self._prev_loss = None
        self.screen_state = "puzzle"
        try:
            self.board.set_fen(p["fen"])
        except Exception:
            self.board.reset()
        # NOTE: orientation is deliberately left alone — auto-flipping the
        # board on every puzzle was disorienting. Press F to flip.
        self.san_history.clear()
        self.grades.clear()
        self.last_grade = None
        self.last_move = None
        self.selected = None
        self.legal_for_selected = []
        self.anims.clear()
        self.best_arrow = None
        # No info toast: theme/rating/clock already live in the coach box and
        # banner, and a toast here just covered the top ranks.
        self.toast = None
        self._refresh_check_state()

    def _next_puzzle(self) -> None:
        if not self.puzzle_pool:
            self.puzzle_pool = coach.sample_pool()
        pool = [p for p in self.puzzle_pool
                if profile_mod.tier_of(int(p.get("rating", 1200))) == self.puzzle_tier]
        if not pool:
            pool = self.puzzle_pool
        try:
            _, p = coach.pick_from_pool(pool, self.puzzle_rating,
                                        self.seen_puzzle_ids or None)
        except Exception:
            p = pool[0]
        if len(self.seen_puzzle_ids) >= len(pool) and len(pool) > 1:
            self.seen_puzzle_ids.clear()
            _, p = coach.pick_from_pool(pool, self.puzzle_rating, None)
        self._load_puzzle(p, tier=self.puzzle_tier)

    def enter_tier(self, tier: str) -> None:
        self.puzzle_mode = True
        self.spar_mode = False
        self.puzzle_tier = tier
        if not self.puzzle_pool:
            self.puzzle_pool = coach.sample_pool()
        pool = [p for p in self.puzzle_pool
                if profile_mod.tier_of(int(p.get("rating", 1200))) == tier]
        if not pool:
            pool = self.puzzle_pool
        try:
            _, p = coach.pick_from_pool(pool, self.puzzle_rating,
                                        self.seen_puzzle_ids or None)
        except Exception:
            p = pool[0]
        self._load_puzzle(p, tier=tier)

    def undo(self) -> None:
        if self.anims or self.ai_thinking:
            return
        if self.puzzle_mode or self.spar_mode:
            return  # puzzles/spar are one-shot; use Next instead
        if not self.board.move_stack:
            return
        pops = 1
        if self.mode in ("AI_BLACK", "AI_WHITE") and len(self.board.move_stack) >= 2:
            pops = 2  # take back full round so it's the human's turn again
        for _ in range(pops):
            if self.board.move_stack:
                self.board.pop()
                if self.san_history:
                    self.san_history.pop()
        # drop grades attached to undone positions (AI moves were never graded)
        kept: list[tuple[int, coach.Grade]] = []
        for ply, g in self.grades:
            if ply <= len(self.board.move_stack):
                kept.append((ply, g))
            else:
                self.coach_score -= g.points
                if g.points > 0 and self.coach_streak > 0:
                    self.coach_streak -= 1
        self.grades = kept
        self.last_grade = self.grades[-1][1] if self.grades else None
        self.last_move = self.board.peek() if self.board.move_stack else None
        self.selected = None
        self.legal_for_selected = []
        self.promotion_choices = []
        self.best_arrow = None
        self.toast = None
        self.game_over_alpha = 0.0
        self._refresh_check_state()
        self.sound.move()

    def new_game(self) -> None:
        self.board.reset()
        self.selected = None
        self.legal_for_selected = []
        self.anims.clear()
        self.last_move = None
        self.san_history.clear()
        self.promotion_choices = []
        self.game_over_alpha = 0.0
        self.move_list_scroll = 0
        self.ai_thinking = False
        self.ai_move = None
        self.grades.clear()
        self.last_grade = None
        self.toast = None
        self.best_arrow = None
        self.game_ai = None
        self.game_rated = False
        self._grade_meta.clear()
        self._prev_grade = None
        self._prev_loss = None
        self._pos_shown_at = time.time()
        self._refresh_check_state()
        self.sound.move()

    def _maybe_rate_game(self) -> None:
        """Once per rated game: blend result + move quality into game Elo."""
        if (not self.game_over_text or self.game_rated or self.game_ai is None
                or self.mode not in ("AI_BLACK", "AI_WHITE")
                or self.puzzle_mode or self.spar_mode):
            return
        self.game_rated = True
        user_white = self.mode == "AI_BLACK"
        if self.board.is_checkmate():
            winner_white = self.board.turn == chess.BLACK
            result = 1.0 if winner_white == user_white else 0.0
        else:
            result = 0.5
        losses = [g.cp_loss for _, g in self.grades]
        avg_loss = sum(losses) / len(losses) if losses else -1.0
        calib = profile_mod.calibration_game(self.profile)
        gr_before = self.profile.get("game_rating", profile_mod.GAME_START)
        out = profile_mod.rate_game(self.profile, self.game_ai["rating"], result, avg_loss)
        self.game_over_sub += f" · Elo {out['rating']} ({out['delta']:+d}) vs {self.game_ai['name']}"
        profile_mod.log_attempt({
            "v": 1, "kind": "game_result", "subject": self.subject_id,
            "session": self.session_id, "mode": "game", "calibration": calib,
            "game_id": self._game_id, "ai_name": self.game_ai.get("name"),
            "ai_rating": self.game_ai.get("rating"), "tier": "game",
            "solved": result == 1.0, "terminal": True,
            "result": result, "avg_loss": round(avg_loss, 1) if avg_loss >= 0 else None,
            "moves": len(self.board.move_stack),
            "ms_total": int((time.time() - self._game_start_at) * 1000),
            "pr_before": gr_before, "pr_after": out["rating"], "pr_delta": out["delta"],
        })

    # -- AI (adaptive ladder by default, manual override via G) ------------
    def matched_rung(self) -> dict:
        return profile_mod.match_ai(self.profile.get("game_rating", profile_mod.GAME_START))

    def ai_label(self) -> str:
        if self.ai_level == "auto":
            r = self.matched_rung()
            return f"Auto {r['rating']}"
        lvl = coach.EngineManager.AI_LEVELS.get(self.ai_level)
        return lvl["label"] if lvl else self.ai_level

    def maybe_start_ai(self) -> None:
        if not self.is_ai_turn() or self.ai_thinking:
            return
        self.ai_thinking = True
        snapshot = self.board.copy()
        level = self.ai_level
        if level == "auto":
            rung_rating = (self.game_ai or self.matched_rung())["rating"]
        else:
            rung_rating = 0

        def worker() -> None:
            try:
                if level == "auto":
                    mv = self.coach.choose_move_rated(snapshot, rung_rating)
                else:
                    mv = self.coach.choose_move(snapshot, level)
            except Exception:
                mv = None
            self.ai_move = mv
            # small delay so the move doesn't feel instant + lets anim finish
            time.sleep(0.35)

        self.ai_thread = threading.Thread(target=worker, daemon=True)
        self.ai_thread.start()

    def cycle_ai_level(self) -> None:
        order = ["auto", "easy", "medium", "hard"]
        self.ai_level = order[(order.index(self.ai_level) + 1) % len(order)]
        self.sound.move()

    def poll_ai(self) -> None:
        if self.ai_thinking and self.ai_thread and not self.ai_thread.is_alive():
            self.ai_thinking = False
            mv = self.ai_move
            self.ai_move = None
            self.ai_thread = None
            if mv is not None and mv in self.board.legal_moves and not self.game_over_text:
                self.push_move(mv)

    # -- drawing --------------------------------------------------------
    def draw(self) -> None:
        if self.screen_state == "study":
            self.study_screen.draw()
            return
        self.screen.fill(BG)
        self._draw_bg_glow()
        if self.screen_state == "home":
            self._draw_home()
        elif self.screen_state == "tiers":
            self._draw_tiers()
        elif self.screen_state == "profile":
            self._draw_profile()
        else:
            self._draw_board()
            self._draw_best_arrow()
            self._draw_pieces_and_anims()
            self._draw_panel()
            self._draw_toast()
            if self.puzzle_mode and self.puzzle_status == "solving":
                self._draw_clock()
            if self.promotion_choices:
                self._draw_promotion_dialog()
            if self.game_over_text:
                self._draw_game_over()
            if self.ai_thinking:
                self._draw_thinking()
        pygame.display.flip()

    # -- screens: home / tiers / profile ----------------------------------
    def _screen_title(self, text: str, y: int = 90) -> None:
        t = pygame.font.SysFont("helveticaneue", 64, bold=True).render(text, True, TEXT)
        self.screen.blit(t, ((WIN_W - t.get_width()) / 2, y))

    def _draw_home(self) -> None:
        self._screen_title("Chesso")
        sub = self.font_ui.render("play chess · practice puzzles · take part in a study",
                                  True, MUTED)
        self.screen.blit(sub, ((WIN_W - sub.get_width()) / 2, 170))
        rung = self.matched_rung()
        tiles = [
            ("play", "Play (1)",
             f"Elo {self.profile.get('game_rating', 400)} · next: {rung['name']} {rung['rating']}",
             "Rated vs adaptive AI"),
            ("puzzles", "Puzzles (2)",
             f"Elo {self.puzzle_rating} · 60-120s clocks",
             "Easy / Medium / Hard tiers"),
            ("profile", "Profile (3)",
             f"{self.profile.get('puzzles_solved', 0)} solves · {self.profile.get('game_games', 0)} games",
             "Ratings, stats & data"),
        ]
        self.home_tiles = []
        tw, th, gap = 280, 190, 28
        x0 = (WIN_W - (3 * tw + 2 * gap)) / 2
        y0 = 250
        mx, my = pygame.mouse.get_pos()
        for i, (key, title, l1, l2) in enumerate(tiles):
            r = pygame.Rect(x0 + i * (tw + gap), y0, tw, th)
            hov = r.collidepoint(mx, my)
            pygame.draw.rect(self.screen, (52, 56, 86) if hov else (36, 38, 60), r, border_radius=16)
            pygame.draw.rect(self.screen, ACCENT if hov else (70, 72, 100), r, 2, border_radius=16)
            t1 = self.font_title.render(title, True, TEXT)
            self.screen.blit(t1, (r.x + (tw - t1.get_width()) / 2, r.y + 28))
            for j, ln in enumerate((l1, l2)):
                s = self.font_ui.render(ln, True, MUTED if j else TEXT)
                self.screen.blit(s, (r.x + (tw - s.get_width()) / 2, r.y + 84 + j * 30))
            self.home_tiles.append((r, key))
        how = [
            "How it works: every human move is graded (Best +10 … Blunder −15).",
            "Play: your rating moves with results AND move quality vs adaptive AI.",
            "Puzzles: beat the clock — first-try Best +10%, decent try +3, timeout fails.",
        ]
        for j, ln in enumerate(how):
            s = self.font_small.render(ln, True, MUTED)
            self.screen.blit(s, ((WIN_W - s.get_width()) / 2, 480 + j * 24))
        study_rect = pygame.Rect((WIN_W-560)//2, 578, 560, 58)
        pygame.draw.rect(self.screen, (38, 58, 84), study_rect, border_radius=12)
        pygame.draw.rect(self.screen, ACCENT, study_rect, 1, border_radius=12)
        study_text = self.font_ui_b.render("Research study (4) · choices, hints & independent learning", True, TEXT)
        self.screen.blit(study_text, study_text.get_rect(center=study_rect.center))
        self.home_tiles.append((study_rect, "study"))
        hint = self.font_ui.render("1 play · 2 puzzles · 3 profile · 4 research study", True, MUTED)
        self.screen.blit(hint, ((WIN_W - hint.get_width()) / 2, WIN_H - 90))

    def _draw_tiers(self) -> None:
        self._screen_title("Puzzles", 60)
        sub = self.font_ui.render(f"your puzzle rating {self.puzzle_rating} — pick a tier",
                                  True, MUTED)
        self.screen.blit(sub, ((WIN_W - sub.get_width()) / 2, 140))
        counts: dict[str, int] = {"easy": 0, "medium": 0, "hard": 0}
        for p in self.puzzle_pool:
            counts[profile_mod.tier_of(int(p.get("rating", 1200)))] += 1
        descs = {
            "easy": ("Easy", "<1000 · 60s · 10 pts"),
            "medium": ("Medium", "1000–1400 · 90s · 20 pts"),
            "hard": ("Hard", ">1400 · 120s · 30 pts"),
        }
        self.tier_cards = []
        tw, th, gap = 280, 190, 28
        x0 = (WIN_W - (3 * tw + 2 * gap)) / 2
        y0 = 210
        mx, my = pygame.mouse.get_pos()
        for i, tier in enumerate(("easy", "medium", "hard")):
            r = pygame.Rect(x0 + i * (tw + gap), y0, tw, th)
            hov = r.collidepoint(mx, my)
            pygame.draw.rect(self.screen, (52, 56, 86) if hov else (36, 38, 60), r, border_radius=16)
            pygame.draw.rect(self.screen, ACCENT if hov else (70, 72, 100), r, 2, border_radius=16)
            title, info = descs[tier]
            dot_col = {"easy": GREEN, "medium": YELLOW, "hard": RED}[tier]
            t1 = self.font_title.render(title, True, TEXT)
            row_w = 14 + 10 + t1.get_width()
            dx0 = r.x + (tw - row_w) / 2
            pygame.draw.circle(self.screen, dot_col, (int(dx0 + 7), int(r.y + 28 + 18)), 9)
            self.screen.blit(t1, (dx0 + 14 + 10, r.y + 28))
            s1 = self.font_ui.render(info, True, TEXT)
            self.screen.blit(s1, (r.x + (tw - s1.get_width()) / 2, r.y + 84))
            s2 = self.font_ui.render(f"{counts[tier]} puzzles", True, MUTED)
            self.screen.blit(s2, (r.x + (tw - s2.get_width()) / 2, r.y + 118))
            self.tier_cards.append((r, tier))
        self.back_button = pygame.Rect((WIN_W - 200) / 2, 450, 200, 44)
        hov = self.back_button.collidepoint(mx, my)
        pygame.draw.rect(self.screen, (46, 48, 70) if not hov else (60, 63, 90),
                         self.back_button, border_radius=10)
        t = self.font_ui.render("< Home (Esc)", True, TEXT)
        self.screen.blit(t, (self.back_button.x + (200 - t.get_width()) / 2,
                             self.back_button.y + 10))

    def _draw_profile(self) -> None:
        self._screen_title("Profile", 50)
        p = self.profile
        lines = [
            f"Subject  {self.subject_id}   (anonymous, local only)",
            f"Game rating  {p.get('game_rating', 400)}  over {p.get('game_games', 0)} rated games",
            f"Puzzle rating  {p.get('puzzle_rating', 800)}  ·  "
            f"{p.get('puzzles_solved', 0)}/{p.get('puzzles_attempted', 0)} solved",
            "Tier solves  " + "  ".join(
                f"{t}: {p.get('tier_solves', {}).get(t, 0)}"
                for t in ("easy", "medium", "hard")),
            f"Points  {p.get('points_total', 0)}   ·   best streak {p.get('best_streak', 0)}",
        ]
        try:
            import os as _os
            nrows = sum(1 for _ in open(profile_mod.ATTEMPTS_FILE)) \
                if _os.path.exists(profile_mod.ATTEMPTS_FILE) else 0
        except Exception:
            nrows = 0
        lines.append(f"Research rows logged  {nrows}  (data/attempts.jsonl, schema v1)")
        y = 150
        for ln in lines:
            s = self.font_ui.render(ln, True, TEXT)
            self.screen.blit(s, ((WIN_W - s.get_width()) / 2, y))
            y += 36
        y += 8
        hdr = self.font_small.render("RECENT", True, MUTED)
        self.screen.blit(hdr, ((WIN_W - hdr.get_width()) / 2, y))
        y += 26
        for h in p.get("history", [])[-8:]:
            if h.get("kind") == "game":
                res = {1.0: "win", 0.5: "draw", 0.0: "loss"}.get(h.get("result"), "?")
                txt = f"game vs {h.get('ai')} · {res} · {h.get('delta', 0):+d} to {h.get('rating')}"
            else:
                txt = (f"puzzle {h.get('puzzle')} ({h.get('tier') or '?'}) · "
                       f"{'solved' if h.get('solved') else 'missed'} · "
                       f"{h.get('delta', 0):+d} to {h.get('rating')}")
            s = self.font_small.render(txt, True, MUTED)
            self.screen.blit(s, ((WIN_W - s.get_width()) / 2, y))
            y += 24
        self.back_button = pygame.Rect((WIN_W - 200) / 2, WIN_H - 100, 200, 44)
        mx, my = pygame.mouse.get_pos()
        hov = self.back_button.collidepoint(mx, my)
        pygame.draw.rect(self.screen, (46, 48, 70) if not hov else (60, 63, 90),
                         self.back_button, border_radius=10)
        t = self.font_ui.render("< Home (Esc)", True, TEXT)
        self.screen.blit(t, (self.back_button.x + (200 - t.get_width()) / 2,
                             self.back_button.y + 10))

    def _draw_clock(self) -> None:
        # Thin bar in the margin ABOVE the board (it used to hang half-clipped
        # off the bottom of the window).
        frac = max(0.0, (self.puzzle_deadline - time.time())
                   / max(1, profile_mod.TIERS[self.puzzle_tier]["time"]))
        w = BOARD_PX
        x = BOARD_X
        y = BOARD_Y - 30  # clear of the board's outer border (starts at BOARD_Y-12)
        pygame.draw.rect(self.screen, (22, 23, 36), (x, y, w, 14), border_radius=7)
        col = GREEN if frac > 0.5 else (YELLOW if frac > 0.25 else RED)
        pygame.draw.rect(self.screen, col, (x, y, max(2, w * frac), 14), border_radius=7)

    def _material_words(self) -> str:
        _, _, mat = self.captured_and_material()
        if mat == 0:
            base = "Even material"
        else:
            side = "White" if mat > 0 else "Black"
            base = f"{side} +{abs(mat) / 100:g}"
        if self.last_grade:
            g = self.last_grade
            return f"{base} · last: {g.label} {g.played_san}"
        return base

    def _draw_best_arrow(self) -> None:
        if not self.best_arrow:
            return
        frm, to, exp = self.best_arrow
        if time.time() > exp:
            self.best_arrow = None
            return
        # fade in last second
        alpha = 230
        remain = exp - time.time()
        if remain < 1.0:
            alpha = int(230 * remain)
        x1, y1 = self.square_center(frm)
        x2, y2 = self.square_center(to)
        dx, dy = x2 - x1, y2 - y1
        dist = math.hypot(dx, dy) or 1
        ux, uy = dx / dist, dy / dist
        # shorten so arrowhead doesn't cover piece
        ex, ey = x2 - ux * self.sq_size * 0.28, y2 - uy * self.sq_size * 0.28
        sx, sy = x1 + ux * self.sq_size * 0.2, y1 + uy * self.sq_size * 0.2
        layer = pygame.Surface((WIN_W, WIN_H), pygame.SRCALPHA)
        col = (110, 200, 130, alpha)
        pygame.draw.line(layer, col, (sx, sy), (ex, ey), 10)
        # arrowhead
        ah = self.sq_size * 0.32
        px, py = -uy, ux
        p1 = (ex + ux * ah, ey + uy * ah)
        p2 = (ex + px * ah * 0.7, ey + py * ah * 0.7)
        p3 = (ex - px * ah * 0.7, ey - py * ah * 0.7)
        pygame.draw.polygon(layer, col, [p1, p2, p3])
        pygame.draw.circle(layer, (110, 200, 130, alpha),
                           (int(sx), int(sy)), 9)
        self.screen.blit(layer, (0, 0))

    def _draw_toast(self) -> None:
        if not self.toast:
            return
        text, color, (cx, cy), born = self.toast
        age = time.time() - born
        if age > 2.4:
            self.toast = None
            return
        rise = min(34, age * 26)
        alpha = 255 if age < 1.6 else int(255 * (2.4 - age) / 0.8)
        font = self.font_ui_b
        surf = font.render(text, True, color)
        bg = pygame.Surface((surf.get_width() + 24, surf.get_height() + 12),
                            pygame.SRCALPHA)
        pygame.draw.rect(bg, (12, 12, 22, min(220, alpha)), bg.get_rect(),
                         border_radius=9)
        bg.set_alpha(alpha)
        # need per-element alpha: blit text with alpha via copy
        txt = surf.copy()
        txt.set_alpha(alpha)
        bg.blit(txt, (12, 6))
        self.screen.blit(bg, (cx - bg.get_width() / 2, cy - self.sq_size - rise))

    def _draw_bg_glow(self) -> None:
        t = (time.time() - self.start_time)
        pulse = 18 + 6 * math.sin(t * 0.7)
        glow = pygame.Surface((WIN_W, WIN_H), pygame.SRCALPHA)
        pygame.draw.circle(glow, (60, 70, 140, 40),
                           (BOARD_X + BOARD_PX // 2, BOARD_Y + BOARD_PX // 2),
                           int(BOARD_PX * 0.75 + pulse))
        self.screen.blit(glow, (0, 0))

    def _draw_board(self) -> None:
        # drop shadow + rounded frame
        outer = pygame.Rect(BOARD_X - 12, BOARD_Y - 12, BOARD_PX + 24, BOARD_PX + 24)
        shadow = pygame.Surface((outer.w + 24, outer.h + 24), pygame.SRCALPHA)
        pygame.draw.rect(shadow, (0, 0, 0, 100), shadow.get_rect(), border_radius=18)
        self.screen.blit(shadow, (outer.x - 12, outer.y - 10))
        pygame.draw.rect(self.screen, (40, 42, 63), outer, border_radius=14)
        pygame.draw.rect(self.screen, (66, 68, 96), outer, 1, border_radius=14)

        sq = self.sq_size
        t = time.time()
        for rank_i in range(8):
            for file_i in range(8):
                x = BOARD_X + file_i * sq
                y = BOARD_Y + rank_i * sq
                # map display -> real square
                if self.orientation_white:
                    f, r = file_i, 7 - rank_i
                else:
                    f, r = 7 - file_i, rank_i
                real = chess.square(f, r)
                light = (f + r) % 2 == 1
                base = LIGHT_SQ if light else DARK_SQ
                if real == self.hover_sq:
                    base = LIGHT_SQ_HOVER if light else DARK_SQ_HOVER
                pygame.draw.rect(self.screen, base, (x, y, sq + 1, sq + 1))

                # last-move highlight (soft warm tint)
                if self.last_move and real in (self.last_move.from_square, self.last_move.to_square):
                    hl = pygame.Surface((sq, sq), pygame.SRCALPHA)
                    hl.fill((LAST_MOVE_HL[0], LAST_MOVE_HL[1], LAST_MOVE_HL[2], 80))
                    self.screen.blit(hl, (x, y))

                # selected highlight (soft, steady — no harsh pulse)
                if real == self.selected:
                    hl = pygame.Surface((sq, sq), pygame.SRCALPHA)
                    hl.fill((110, 200, 130, 90))
                    self.screen.blit(hl, (x, y))
                    pygame.draw.rect(self.screen, (105, 210, 140), (x + 2, y + 2, sq - 4, sq - 4), 2, border_radius=8)

                # check highlight (red radial pulse)
                if real == self.king_in_check_sq:
                    pulse = 0.5 + 0.5 * math.sin(t * 7)
                    glow = pygame.Surface((sq, sq), pygame.SRCALPHA)
                    pygame.draw.circle(glow, (235, 60, 60, int(120 + 80 * pulse)),
                                       (sq / 2, sq / 2), sq * (0.32 + 0.06 * pulse))
                    pygame.draw.circle(glow, (255, 120, 120, 200), (sq / 2, sq / 2), sq * 0.22)
                    self.screen.blit(glow, (x, y))

                # coordinates on a-file / 1st rank edges (high-contrast, subtle)
                if file_i == 0:
                    label = str(r + 1)
                    col = (150, 110, 75) if light else (237, 214, 179)
                    txt = self.font_small.render(label, True, col)
                    self.screen.blit(txt, (x + 6, y + 5))
                if rank_i == 7:
                    label = chr(ord("a") + f)
                    col = (150, 110, 75) if light else (237, 214, 179)
                    txt = self.font_small.render(label, True, col)
                    self.screen.blit(txt, (x + sq - 17, y + sq - 21))

        # legal move dots / rings
        for m in self.legal_for_selected:
            cx, cy = self.square_center(m.to_square)
            is_cap = self.board.piece_at(m.to_square) is not None or self.board.is_en_passant(m)
            hovered = m.to_square == self.hover_sq
            if is_cap:
                rad = sq * (0.46 if hovered else 0.42)
                ring = pygame.Surface((sq, sq), pygame.SRCALPHA)
                pygame.draw.circle(ring, (235, 90, 90, 210), (sq / 2, sq / 2), rad, 5)
                if hovered:
                    pygame.draw.circle(ring, (235, 90, 90, 90), (sq / 2, sq / 2), rad - 4)
                self.screen.blit(ring, (cx - sq / 2, cy - sq / 2))
            else:
                rad = sq * (0.20 if hovered else 0.16)
                dot = pygame.Surface((sq, sq), pygame.SRCALPHA)
                pygame.draw.circle(dot, (30, 40, 30, 110), (sq / 2 + 2, sq / 2 + 3), rad)
                pygame.draw.circle(dot, (40, 90, 55, 200), (sq / 2, sq / 2), rad)
                pygame.draw.circle(dot, (200, 255, 210, 220), (sq / 2, sq / 2), rad * 0.45)
                self.screen.blit(dot, (cx - sq / 2, cy - sq / 2))

    def _draw_pieces_and_anims(self) -> None:
        sq = self.sq_size
        hidden_from = {a.to_px for a in self.anims}  # not needed; we track squares below
        anim_squares_to: set[chess.Square] = set()
        anim_squares_from: set[chess.Square] = set()
        # We hide pieces that are currently animating by tracking their
        # from/to squares via reverse lookup of pixel -> square.
        for a in self.anims:
            pass
        # Simplest: hide destination squares of anims + source piece already moved in board state.
        # Since board.push already happened, the moving piece is at to_square in the
        # board, so we skip drawing pieces on any to_square covered by an anim and
        # draw the anim instead.
        anim_targets: list[tuple[float, float]] = [(a.to_px[0], a.to_px[1]) for a in self.anims]

        def is_anim_target(cx: float, cy: float) -> bool:
            for ax, ay in anim_targets:
                if abs(ax - cx) < 2 and abs(ay - cy) < 2:
                    return True
            return False

        for sqi in chess.SQUARES:
            piece = self.board.piece_at(sqi)
            if piece is None:
                continue
            cx, cy = self.square_center(sqi)
            if is_anim_target(cx, cy) and any(True for _ in [1]):
                # If an anim ends exactly here, the anim draws it; skip static.
                # (For castling there are two anims; both covered.)
                continue
            # dragging piece follows mouse
            if self.dragging and sqi == self.drag_from and self.drag_from is not None:
                continue
            surf = self.renderer.get(piece.piece_type, piece.color)
            origin_from_anim = False
            # hide pieces on squares an anim just left? No — board state already
            # moved them, so from-squares are naturally empty. Nothing to do.
            self.screen.blit(surf, (cx - surf.get_width() / 2, cy - surf.get_height() / 2 + 2))

        # captures fade out while mover slides
        for a in self.anims:
            e = ease_in_out_cubic(a.t / max(1e-6, a.duration))
            mx = a.from_px[0] + (a.to_px[0] - a.from_px[0]) * e
            # little hop arc for knights / castles
            hop = 0.0
            if a.piece_type == chess.KNIGHT:
                hop = -22 * math.sin(math.pi * e)
            my = a.from_px[1] + (a.to_px[1] - a.from_px[1]) * e + hop
            if a.captured_surf is not None and a.captured_px is not None:
                fade = 1.0 - e
                cs = a.captured_surf.copy()
                cs.set_alpha(int(255 * fade))
                scale = 1.0 - 0.35 * e
                w, h = cs.get_size()
                cs = pygame.transform.smoothscale(cs, (max(1, int(w * scale)), max(1, int(h * scale))))
                self.screen.blit(cs, (a.captured_px[0] - cs.get_width() / 2,
                                      a.captured_px[1] - cs.get_height() / 2))
            # moving piece with shadow that grows mid-flight
            surf = self.renderer.get(a.piece_type, a.color)
            lift = math.sin(math.pi * e) * 6
            sh = pygame.Surface((sq, sq * 0.35), pygame.SRCALPHA)
            pygame.draw.ellipse(sh, (0, 0, 0, int(70 + 60 * math.sin(math.pi * e))),
                                (sq * 0.15, 0, sq * 0.7, sq * 0.32))
            self.screen.blit(sh, (mx - sq / 2, my + sq * 0.22 - lift * 0.3))
            self.screen.blit(surf, (mx - surf.get_width() / 2, my - surf.get_height() / 2 + 2 - lift))

        # dragged piece on top
        if self.dragging and self.drag_from is not None:
            piece = self.board.piece_at(self.drag_from)
            # during drag the piece is still on its square in board state
            if piece is not None:
                surf = self.renderer.get(piece.piece_type, piece.color)
                mx, my = self.drag_pos
                sh = pygame.Surface((sq, sq * 0.4), pygame.SRCALPHA)
                pygame.draw.ellipse(sh, (0, 0, 0, 120), (sq * 0.12, 0, sq * 0.76, sq * 0.34))
                self.screen.blit(sh, (mx - sq / 2, my + sq * 0.2))
                big = pygame.transform.smoothscale(
                    surf, (int(surf.get_width() * 1.08), int(surf.get_height() * 1.08)))
                self.screen.blit(big, (mx - big.get_width() / 2, my - big.get_height() / 2 - 6))

        _ = hidden_from, anim_squares_to, anim_squares_from, origin_from_anim

    # -- side panel -----------------------------------------------------
    def captured_and_material(self) -> tuple[list, list, int]:
        # material from piece_map diff vs starting position
        start_counts: dict[tuple[int, bool], int] = {}
        for pt in (chess.PAWN, chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN):
            start_counts[(pt, chess.WHITE)] = {chess.PAWN: 8, chess.KNIGHT: 2, chess.BISHOP: 2, chess.ROOK: 2, chess.QUEEN: 1}[pt]
            start_counts[(pt, chess.BLACK)] = start_counts[(pt, chess.WHITE)]
        cur: dict[tuple[int, bool], int] = {}
        for sq in chess.SQUARES:
            p = self.board.piece_at(sq)
            if p and p.piece_type != chess.KING:
                cur[(p.piece_type, p.color)] = cur.get((p.piece_type, p.color), 0) + 1
        white_caps, black_caps = [], []  # pieces white captured (black pieces), etc.
        for (pt, color), n0 in start_counts.items():
            missing = n0 - cur.get((pt, color), 0)
            for _ in range(max(0, missing)):
                if color == chess.BLACK:
                    white_caps.append(pt)  # white captured these
                else:
                    black_caps.append(pt)
        order = {chess.QUEEN: 0, chess.ROOK: 1, chess.BISHOP: 2, chess.KNIGHT: 3, chess.PAWN: 4}
        white_caps.sort(key=lambda p: order[p])
        black_caps.sort(key=lambda p: order[p])
        mat = sum(PIECE_VALUES[p] for p in white_caps) - sum(PIECE_VALUES[p] for p in black_caps)
        return white_caps, black_caps, mat

    def _draw_panel(self) -> None:
        panel = pygame.Rect(PANEL_X, BOARD_Y - 8, PANEL_W, BOARD_PX + 16)
        pygame.draw.rect(self.screen, PANEL_BG, panel, border_radius=14)
        pygame.draw.rect(self.screen, (62, 64, 92), panel, 1, border_radius=14)

        # title (plain text — chess glyphs/emoji lack coverage in UI fonts)
        title = self.font_title.render("Chesso", True, TEXT)
        self.screen.blit(title, (PANEL_X + 18, BOARD_Y + 4))
        sub = self.font_small.render("pygame · python-chess", True, MUTED)
        self.screen.blit(sub, (PANEL_X + 20, BOARD_Y + 38))
        self.home_button = pygame.Rect(PANEL_X + PANEL_W - 92, BOARD_Y + 4, 76, 30)
        mx0, my0 = pygame.mouse.get_pos()
        hov0 = self.home_button.collidepoint(mx0, my0)
        pygame.draw.rect(self.screen, (60, 63, 90) if hov0 else (46, 48, 70),
                         self.home_button, border_radius=8)
        ht = self.font_small.render("Home", True, TEXT)
        self.screen.blit(ht, (self.home_button.x + (76 - ht.get_width()) / 2,
                              self.home_button.y + 7))

        # turn banner
        white_to_move = self.board.turn == chess.WHITE
        banner = pygame.Rect(PANEL_X + 14, BOARD_Y + 62, PANEL_W - 28, 52)
        pygame.draw.rect(self.screen, (44, 46, 66), banner, border_radius=10)
        dot_c = (242, 242, 246) if white_to_move else (22, 22, 30)
        ring_c = (130, 132, 150) if white_to_move else (170, 172, 190)
        pygame.draw.circle(self.screen, dot_c, (banner.x + 26, banner.y + 26), 12)
        pygame.draw.circle(self.screen, ring_c, (banner.x + 26, banner.y + 26), 12, 2)
        if self.game_over_text:
            line1, col = self.game_over_text, YELLOW
        elif self.board.is_check():
            line1, col = f"{'White' if white_to_move else 'Black'} to move · CHECK!", RED
        else:
            line1, col = f"{'White' if white_to_move else 'Black'} to move", TEXT
        t1 = self.font_ui_b.render(line1, True, col)
        self.screen.blit(t1, (banner.x + 48, banner.y + 7))
        mode_label = {"2P": "2 players · local", "AI_BLACK": "You: White · AI: Black",
                      "AI_WHITE": "You: Black · AI: White"}[self.mode]
        if self.mode != "2P":
            mode_label += f" · {self.ai_label()}"
        if self.spar_mode and self.puzzle:
            themes = " ".join((self.puzzle.get("themes") or ["spar"])[:2])
            mode_label = (f"Spar {themes} · {self.spar_moves}/{self.spar_target}")
        elif self.puzzle_mode and self.puzzle:
            themes = " ".join((self.puzzle.get("themes") or ["puzzle"])[:2])
            mode_label = (f"Puzzle {themes} · Elo {self.puzzle.get('rating', '?')}")
        extra = ""
        if self.ai_thinking:
            extra = " · AI thinking…"
        elif self.spar_pending_compute:
            extra = " · sparring…"
        t2 = self.font_small.render(mode_label + extra, True, MUTED)
        self.screen.blit(t2, (banner.x + 48, banner.y + 30))

        # AI mode + difficulty buttons (split row)
        ab = self.ai_button
        ab.y = BOARD_Y + 122
        ab.w = int((PANEL_W - 28) * 0.62)
        lb = self.ai_level_button
        lb.x, lb.y = ab.x + ab.w + 8, ab.y
        lb.w, lb.h = PANEL_W - 28 - ab.w - 8, 36
        mx, my = pygame.mouse.get_pos()
        hov = ab.collidepoint(mx, my)
        pygame.draw.rect(self.screen, (52, 90, 150) if hov else (46, 78, 132), ab, border_radius=9)
        label = {  # current mode; (A) cycles
            "2P": "2P local (A)",
            "AI_BLACK": "You W · AI B (A)",
            "AI_WHITE": "You B · AI W (A)",
        }[self.mode]
        # cycle 2P -> AI_BLACK -> AI_WHITE -> 2P
        tx = self.font_ui.render(label, True, (235, 242, 255))
        self.screen.blit(tx, (ab.x + 14, ab.y + 8))
        hov2 = lb.collidepoint(mx, my)
        pygame.draw.rect(self.screen, (52, 90, 150) if hov2 else (46, 78, 132), lb, border_radius=9)
        tx2 = self.font_ui.render(f"{self.ai_label()} (G)", True, (235, 242, 255))
        self.screen.blit(tx2, (lb.x + (lb.w - tx2.get_width()) / 2, lb.y + 8))

        # captured pieces
        wcaps, bcaps, mat = self.captured_and_material()
        cy = BOARD_Y + 172
        self.screen.blit(self.font_small.render("Captured", True, MUTED), (PANEL_X + 16, cy))
        adv = ""
        if mat > 0:
            adv = f"White +{mat / 100:g}"
        elif mat < 0:
            adv = f"Black +{-mat / 100:g}"
        if adv:
            at = self.font_small.render(adv, True, GREEN)
            self.screen.blit(at, (PANEL_X + PANEL_W - 16 - at.get_width(), cy))
        self._draw_captured_row(wcaps, chess.BLACK, PANEL_X + 16, cy + 20)
        self._draw_captured_row(bcaps, chess.WHITE, PANEL_X + 16, cy + 46)
        # plain-words verdict for beginners (material + last graded move)
        vw = self.font_small.render(self._material_words()[:52], True, ACCENT)
        self.screen.blit(vw, (PANEL_X + 16, cy + 70))

        # move list
        ly = cy + 92
        self.screen.blit(self.font_small.render("Moves  ·  scroll with wheel", True, MUTED), (PANEL_X + 16, ly))
        list_rect = pygame.Rect(PANEL_X + 14, ly + 20, PANEL_W - 28, 156)
        pygame.draw.rect(self.screen, (22, 23, 36), list_rect, border_radius=10)
        # clip
        self.screen.set_clip(list_rect)
        y0 = list_rect.y + 10 - self.move_list_scroll
        for i in range(0, len(self.san_history), 2):
            n = i // 2 + 1
            w = self.san_history[i] if i < len(self.san_history) else ""
            b = self.san_history[i + 1] if i + 1 < len(self.san_history) else ""
            row_y = y0 + (i // 2) * 26
            if row_y < list_rect.y - 26 or row_y > list_rect.bottom + 10:
                continue
            is_last = (i + 1 == len(self.san_history) - 1) or (i == len(self.san_history) - 1 and not b)
            if is_last:
                hl = pygame.Surface((list_rect.w - 12, 24), pygame.SRCALPHA)
                hl.fill((129, 182, 255, 40))
                self.screen.blit(hl, (list_rect.x + 6, row_y - 3))
            num = self.font_moves.render(f"{n}.", True, MUTED)
            wm = self.font_moves.render(w, True, TEXT)
            bm = self.font_moves.render(b, True, TEXT)
            self.screen.blit(num, (list_rect.x + 12, row_y))
            self.screen.blit(wm, (list_rect.x + 52, row_y))
            self.screen.blit(bm, (list_rect.x + 150, row_y))
        if not self.san_history:
            hint = self.font_small.render("-- no moves yet --", True, (90, 92, 115))
            self.screen.blit(hint, (list_rect.x + 12, y0))
        self.screen.set_clip(None)

        # --- Coach box (ChessTempo-style) --------------------------------
        co_y = list_rect.bottom + 10
        co_rect = pygame.Rect(PANEL_X + 14, co_y, PANEL_W - 28, 108)
        pygame.draw.rect(self.screen, (22, 23, 36), co_rect, border_radius=10)
        pygame.draw.rect(self.screen, (62, 64, 92), co_rect, 1, border_radius=10)
        backend = self.coach.backend if hasattr(self, "coach") else "local"
        head = f"COACH · {backend} · Score {self.coach_score} · Streak {self.coach_streak}"
        if self.puzzle_mode and self.puzzle:
            themes = " ".join((self.puzzle.get("themes") or ["tactic"])[:2])
            sol = self.puzzle.get("solution") or []
            total = (len(sol) + 1) // 2
            done = min(total, (self.puzzle_ply + 1) // 2)
            secs = max(0, int(self.puzzle_deadline - time.time()))
            head = (f"{themes} · {self.puzzle.get('rating', '?')} "
                    f"· you {self.puzzle_rating} · {done}/{total} "
                    f"· {secs}s · {self.puzzle_status}")
        elif self.spar_mode and self.puzzle:
            themes = " ".join((self.puzzle.get("themes") or ["tactic"])[:2])
            head = (f"SPAR {themes} · {self.puzzle.get('rating', '?')} "
                    f"· you {self.puzzle_rating} · "
                    f"{min(self.spar_moves, self.spar_target)}/{self.spar_target} "
                    f"· {self.puzzle_status}")
        self.screen.blit(self.font_small.render(head, True, MUTED),
                         (co_rect.x + 10, co_rect.y + 6))
        if self.last_grade:
            g = self.last_grade
            col = coach.LABEL_COLORS.get(g.label, TEXT)
            line = f"{g.label} ({g.points:+d})  you {g.played_san} {g.played_eval}"
            self.screen.blit(self.font_ui.render(line, True, col),
                             (co_rect.x + 10, co_rect.y + 24))
            line2 = f"best {g.best_san} {g.best_eval} · loss {g.cp_loss}cp"
            self.screen.blit(self.font_small.render(line2, True, MUTED),
                             (co_rect.x + 10, co_rect.y + 46))
        elif self.grading_busy:
            self.screen.blit(self.font_small.render("Analysing…", True, ACCENT),
                             (co_rect.x + 10, co_rect.y + 26))
        else:
            tip = ("On" if self.coach_enabled else "Off")
            self.screen.blit(self.font_small.render(
                f"Coach {tip} · C toggle · H hint(-5) · P puzzles", True, MUTED),
                (co_rect.x + 10, co_rect.y + 26))
        # coach row buttons
        bw = (co_rect.w - 26) // 4
        self.coach_button = pygame.Rect(co_rect.x + 6, co_rect.y + 68, bw, 30)
        self.hint_button = pygame.Rect(co_rect.x + 9 + bw, co_rect.y + 68, bw, 30)
        self.puzzle_button = pygame.Rect(co_rect.x + 12 + bw * 2, co_rect.y + 68, bw, 30)
        self.spar_button = pygame.Rect(co_rect.x + 15 + bw * 3, co_rect.y + 68, bw, 30)
        for rect, lab in (
            (self.coach_button, f"{'On' if self.coach_enabled else 'Off'} (C)"),
            (self.hint_button, "Hint (H)"),
            (self.puzzle_button,
             "Next" if self.puzzle_mode else "Puzz (P)"),
            (self.spar_button,
             "Next" if self.spar_mode else "Spar (S)"),
        ):
            hov = rect.collidepoint(mx, my)
            pygame.draw.rect(self.screen, (60, 63, 90) if hov else (46, 48, 70),
                             rect, border_radius=7)
            tx = self.font_small.render(lab, True, TEXT)
            self.screen.blit(tx, (rect.x + (rect.w - tx.get_width()) / 2, rect.y + 8))

        # buttons
        for b in self.buttons:
            if b.action == "sound":
                b.label = f"Sound: {'On' if self.sound.enabled else 'Off'}"
            hov = b.rect.collidepoint(mx, my)
            col = (60, 63, 90) if hov else (46, 48, 70)
            pygame.draw.rect(self.screen, col, b.rect, border_radius=9)
            pygame.draw.rect(self.screen, (80, 83, 115), b.rect, 1, border_radius=9)
            tx = self.font_ui.render(b.label, True, TEXT)
            self.screen.blit(tx, (b.rect.x + (b.rect.w - tx.get_width()) / 2, b.rect.y + 8))

        # footer hint — sits in the padding below the buttons, never over them
        footer_y = BOARD_Y + BOARD_PX + 8 - 20
        hint = self.font_small.render("N new  ·  U undo  ·  A mode  ·  G level  ·  D daily", True, MUTED)
        self.screen.blit(hint, (PANEL_X + 16, footer_y))

    def _draw_captured_row(self, pieces: list[int], color: bool, x: int, y: int) -> None:
        # Each captured glyph sits on a contrasting chip so both colors read
        # on the dark panel (dark glyphs were invisible blobs before).
        cx = x
        for pt in pieces:
            chip_bg = (226, 214, 186) if color == chess.BLACK else (44, 46, 66)
            chip_fg = (24, 24, 30) if color == chess.BLACK else (232, 232, 238)
            chip = pygame.Rect(cx - 2, y - 6, 24, 24)
            pygame.draw.rect(self.screen, chip_bg, chip, border_radius=6)
            g = GLYPH[(pt, color)]
            txt = self.font_glyph_small.render(g, True, chip_fg)
            self.screen.blit(txt, (cx + (22 - txt.get_width()) / 2, y - 5))
            cx += 26

    def _draw_promotion_dialog(self) -> None:
        overlay = pygame.Surface((WIN_W, WIN_H), pygame.SRCALPHA)
        overlay.fill((10, 10, 18, 130))
        self.screen.blit(overlay, (0, 0))
        assert self.promo_to is not None
        cx, cy = self.square_center(self.promo_to)
        sq = self.sq_size
        box_w, box_h = sq * 4 + 24, sq + 52
        bx = min(max(cx - box_w / 2, BOARD_X), BOARD_X + BOARD_PX - box_w)
        by = min(max(cy - box_h / 2, BOARD_Y), BOARD_Y + BOARD_PX - box_h)
        box = pygame.Rect(bx, by, box_w, box_h)
        pygame.draw.rect(self.screen, (36, 38, 58), box, border_radius=12)
        pygame.draw.rect(self.screen, (90, 92, 120), box, 1, border_radius=12)
        ttl = self.font_ui_b.render("Promote to:", True, TEXT)
        self.screen.blit(ttl, (bx + 14, by + 8))
        order = [chess.QUEEN, chess.ROOK, chess.BISHOP, chess.KNIGHT]
        self.promo_rects: list[tuple[pygame.Rect, chess.Move]] = []
        for i, pt in enumerate(order):
            mv = next((m for m in self.promotion_choices if m.promotion == pt), None)
            if mv is None:
                continue
            r = pygame.Rect(bx + 12 + i * sq, by + 32, sq - 6, sq - 6)
            mx, my = pygame.mouse.get_pos()
            if r.collidepoint(mx, my):
                pygame.draw.rect(self.screen, (70, 90, 140), r, border_radius=8)
            else:
                pygame.draw.rect(self.screen, LIGHT_SQ if i % 2 == 0 else DARK_SQ, r, border_radius=8)
            surf = self.renderer.get(pt, self.board.turn)
            sc = pygame.transform.smoothscale(surf, (int(sq * 0.8), int(sq * 0.8)))
            self.screen.blit(sc, (r.centerx - sc.get_width() / 2, r.centery - sc.get_height() / 2))
            self.promo_rects.append((r, mv))

    def _draw_game_over(self) -> None:
        target = 200
        self.game_over_alpha = min(target, self.game_over_alpha + 3.5)
        bw, bh = 460, 116
        bx = BOARD_X + (BOARD_PX - bw) / 2
        by = BOARD_Y + BOARD_PX // 2 - bh / 2
        card = pygame.Surface((bw, bh), pygame.SRCALPHA)
        pygame.draw.rect(card, (16, 17, 28, int(self.game_over_alpha)),
                         card.get_rect(), border_radius=14)
        self.screen.blit(card, (bx, by))
        pygame.draw.rect(self.screen, (90, 92, 120), (bx, by, bw, bh), 1, border_radius=14)
        t1 = self.font_ui_b.render(self.game_over_text, True, (255, 255, 255))
        t2 = self.font_small.render(self.game_over_sub, True, MUTED)
        self.screen.blit(t1, (bx + (bw - t1.get_width()) / 2, by + 28))
        self.screen.blit(t2, (bx + (bw - t2.get_width()) / 2, by + 60))

    def _draw_thinking(self) -> None:
        # Banner subtitle already shows thinking state; draw a small pill
        # on the board so it never overlaps panel text.
        dots = int(time.time() * 4) % 4
        txt = self.font_small.render("AI thinking" + "." * dots, True, (235, 242, 255))
        pad_x, pad_y = 12, 7
        pill = pygame.Surface((txt.get_width() + pad_x * 2, txt.get_height() + pad_y * 2),
                              pygame.SRCALPHA)
        pygame.draw.rect(pill, (46, 78, 132, 235), pill.get_rect(), border_radius=9)
        pill.blit(txt, (pad_x, pad_y))
        self.screen.blit(pill, (BOARD_X + 16, BOARD_Y + 16))

    # -- events ---------------------------------------------------------
    def _go_home_tile(self, key: str) -> None:
        self.sound.move()
        if key == "play":
            self.screen_state = "play"  # resume the board as-is
        elif key == "puzzles":
            self.screen_state = "tiers"
        elif key == "profile":
            self.screen_state = "profile"
        elif key == "study":
            from study_ui import StudyScreen

            self.study_screen = StudyScreen(self, self.study_options)
            self.screen_state = "study"

    def cycle_mode(self) -> None:
        order = ["2P", "AI_BLACK", "AI_WHITE"]
        self.mode = order[(order.index(self.mode) + 1) % len(order)]
        # drop any in-flight AI thought: it belongs to the old mode and must
        # never land a surprise move (this was the "AI never moves" ghost —
        # a stale thought could also sit forever on the wrong side).
        self.ai_thinking = False
        self.ai_thread = None
        self.ai_move = None
        self.sound.move()

    def handle_click(self, pos: tuple[int, int], button: int) -> None:
        x, y = pos
        if self.screen_state == "home":
            for rect, key in self.home_tiles:
                if rect.collidepoint(x, y):
                    self._go_home_tile(key)
                    return
            return
        if self.screen_state == "tiers":
            for rect, tier in self.tier_cards:
                if rect.collidepoint(x, y):
                    self.enter_tier(tier)
                    self.sound.move()
                    return
            if self.back_button.collidepoint(x, y):
                self.screen_state = "home"
                self.sound.move()
            return
        if self.screen_state == "profile":
            if self.back_button.collidepoint(x, y):
                self.screen_state = "home"
                self.sound.move()
            return
        if self.home_button.collidepoint(x, y):
            self.screen_state = "home"
            self.sound.move()
            return
        if self.promotion_choices and hasattr(self, "promo_rects"):
            for rect, mv in self.promo_rects:
                if rect.collidepoint(x, y):
                    self.push_move(mv)
                    return
            return
        # panel buttons
        if self.ai_button.collidepoint(x, y):
            self.cycle_mode()
            return
        if self.ai_level_button.collidepoint(x, y):
            self.cycle_ai_level()
            return
        if self.coach_button.collidepoint(x, y):
            self.coach_enabled = not self.coach_enabled
            self.sound.move()
            return
        if self.hint_button.collidepoint(x, y):
            self.show_hint()
            return
        if self.puzzle_button.collidepoint(x, y):
            if self.puzzle_mode:
                self._next_puzzle()
            elif self.spar_mode:
                self.exit_spar()
                self.screen_state = "tiers"
            else:
                self.screen_state = "tiers"
            self.sound.move()
            return
        if self.spar_button.collidepoint(x, y):
            if self.spar_mode:
                self._next_spar()
            else:
                if self.puzzle_mode:
                    self.exit_puzzle()
                self.enter_spar()
            self.sound.move()
            return
        for b in self.buttons:
            if b.rect.collidepoint(x, y):
                if b.action == "new":
                    if self.puzzle_mode:
                        self.exit_puzzle()
                    elif self.spar_mode:
                        self.exit_spar()
                    else:
                        self.new_game()
                elif b.action == "undo":
                    self.undo()
                elif b.action == "flip":
                    self.orientation_white = not self.orientation_white
                    self.sound.move()
                elif b.action == "sound":
                    self.sound.enabled = not self.sound.enabled
                return
        sq = self.pixel_to_square(x, y)
        if sq is None:
            return
        if button == 3:  # right click = deselect
            self.selected = None
            self.legal_for_selected = []
            return
        if not self.human_can_move() or self._ai_blocks_human():
            return
        piece = self.board.piece_at(sq)
        if self.selected is None:
            if piece and piece.color == self.board.turn:
                self.select(sq)
        else:
            if sq == self.selected:
                self.selected = None
                self.legal_for_selected = []
            else:
                self.attempt_move(self.selected, sq)

    def run(self) -> None:
        self.promo_rects = []
        running = True
        while running:
            dt = self.clock.tick(60) / 1000.0
            for event in pygame.event.get():
                if self.screen_state == "study":
                    if event.type == pygame.QUIT:
                        self.study_screen.leave()
                        running = False
                    elif self.study_screen.handle_event(event):
                        self.screen_state = "home"
                    continue
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.MOUSEMOTION:
                    self.hover_sq = self.pixel_to_square(*event.pos)
                    if self.dragging:
                        self.drag_pos = event.pos
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    if event.button == 1:
                        # maybe start drag (board screens only)
                        sq = self.pixel_to_square(*event.pos)
                        if (self.screen_state in ("play", "puzzle")
                                and sq is not None and not self.promotion_choices
                                and self.human_can_move() and not self._ai_blocks_human()):
                            p = self.board.piece_at(sq)
                            if p and p.color == self.board.turn:
                                self.select(sq)
                                self.dragging = True
                                self.drag_from = sq
                                self.drag_pos = event.pos
                            else:
                                self.handle_click(event.pos, event.button)
                                self.dragging = False
                                self.drag_from = None
                        else:
                            self.handle_click(event.pos, event.button)
                    elif event.button in (3,):
                        self.handle_click(event.pos, event.button)
                    elif event.button == 4:  # wheel up
                        self.move_list_scroll = max(0, self.move_list_scroll - 24)
                    elif event.button == 5:  # wheel down
                        max_scroll = max(0, (len(self.san_history) + 1) // 2 * 26 - 280)
                        self.move_list_scroll = min(max_scroll, self.move_list_scroll + 24)
                elif event.type == pygame.MOUSEBUTTONUP:
                    if event.button == 1 and self.dragging:
                        self.dragging = False
                        target = self.pixel_to_square(*event.pos)
                        frm = self.drag_from
                        self.drag_from = None
                        if frm is not None and target is not None and frm != target:
                            if self.human_can_move() and not self._ai_blocks_human():
                                self.selected = frm
                                self.legal_for_selected = self.legal_moves_from(frm)
                                self.attempt_move(frm, target)
                        # click without drag already selected; keep selection
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        if self.screen_state in ("tiers", "profile"):
                            self.screen_state = "home"
                        elif self.selected is not None or self.promotion_choices:
                            self.selected = None
                            self.legal_for_selected = []
                            self.promotion_choices = []
                        elif self.screen_state in ("play", "puzzle"):
                            self.screen_state = "home"
                    elif event.key == pygame.K_1 and self.screen_state == "home":
                        self._go_home_tile("play")
                    elif event.key == pygame.K_2 and self.screen_state == "home":
                        self._go_home_tile("puzzles")
                    elif event.key == pygame.K_3 and self.screen_state == "home":
                        self._go_home_tile("profile")
                    elif event.key == pygame.K_4 and self.screen_state == "home":
                        self._go_home_tile("study")
                    elif event.key == pygame.K_1 and self.screen_state == "tiers":
                        self.enter_tier("easy")
                    elif event.key == pygame.K_2 and self.screen_state == "tiers":
                        self.enter_tier("medium")
                    elif event.key == pygame.K_3 and self.screen_state == "tiers":
                        self.enter_tier("hard")
                    elif event.key == pygame.K_n:
                        if self.puzzle_mode:
                            if self.puzzle_status in ("solved", "failed"):
                                self._next_puzzle()
                            else:
                                self.exit_puzzle()
                        elif self.spar_mode:
                            if self.puzzle_status in ("solved", "failed"):
                                self._next_spar()
                            else:
                                self.exit_spar()
                        else:
                            self.new_game()
                    elif event.key == pygame.K_u:
                        self.undo()
                    elif event.key == pygame.K_f:
                        self.orientation_white = not self.orientation_white
                    elif event.key == pygame.K_a:
                        self.cycle_mode()
                    elif event.key == pygame.K_c:
                        self.coach_enabled = not self.coach_enabled
                        self.sound.move()
                    elif event.key == pygame.K_h:
                        self.show_hint()
                    elif event.key == pygame.K_p:
                        if self.screen_state == "home":
                            self.screen_state = "tiers"
                        elif self.spar_mode:
                            self.exit_spar()
                            self.screen_state = "tiers"
                        elif self.puzzle_mode:
                            self.exit_puzzle()
                        else:
                            self.screen_state = "tiers"
                        self.sound.move()
                    elif event.key == pygame.K_s:
                        if self.spar_mode:
                            self.exit_spar()
                        else:
                            if self.puzzle_mode:
                                self.exit_puzzle()
                            self.enter_spar()
                        self.sound.move()
                    elif event.key == pygame.K_g:
                        self.cycle_ai_level()
                    elif event.key == pygame.K_d:
                        self.fetch_daily_puzzle()
                        self.sound.move()

            if self.screen_state == "study":
                self.study_screen.update()
                self.draw()
                continue

            # AI
            self.maybe_start_ai()
            self.poll_ai()
            # puzzle opponent auto-reply
            self.fire_pending_reply()
            # puzzle clock → timeout fail
            if (self.puzzle_mode and self.puzzle_status == "solving"
                    and self.puzzle_deadline
                    and time.time() > self.puzzle_deadline):
                self._puzzle_timeout()
            # deferred solve/fail finalization (needs the grade for bonus/verdict)
            if self._solve_pending and (self._pending_meta is None
                                        or time.time() - self._solve_at > 1.5):
                self._finalize_puzzle_solve()
            if (self.puzzle_mode and self.puzzle_status == "failed_pending"
                    and not self.grading_busy
                    and time.time() - self._fail_at > 1.2 and self._fail_uci):
                try:
                    self._puzzle_failed(self._fail_uci, self._reconstruct_before(
                        chess.Move.from_uci(self._fail_uci)))
                except Exception:
                    pass
            # rated game → Elo once the game ends
            self._maybe_rate_game()

            # advance animations
            finished: list[MoveAnim] = []
            for a in self.anims:
                a.t += dt
                if a.t >= a.duration:
                    finished.append(a)
            for a in finished:
                self.anims.remove(a)

            self.draw()
        try:
            self.coach.close()
        except Exception:
            pass
        pygame.quit()


def main() -> None:
    parser = argparse.ArgumentParser(description="Chesso chess game and local research study")
    parser.add_argument("--study", action="store_true", help="open the study screen")
    parser.add_argument("--participant", help="pseudonymous study code")
    parser.add_argument("--condition", choices=("informational", "reflective"))
    parser.add_argument("--protocol", help="path to a frozen study protocol")
    parser.add_argument("--collection", choices=("pilot", "main"), default="pilot")
    parser.add_argument("--resume", help="resume a local study session folder")
    args = parser.parse_args()
    game = ChessGame()
    game.study_options = {key: value for key, value in vars(args).items() if value is not None}
    if args.study or args.resume:
        game._go_home_tile("study")
    game.run()


if __name__ == "__main__":
    main()
