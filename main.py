"""Chesso — a polished pygame + python-chess game.

Run with:
    uv run python main.py
"""

from __future__ import annotations

import array
import math
import threading
import time
from dataclasses import dataclass

import chess
import pygame

import coach

# --------------------------------------------------------------------------
# Config / theme
# --------------------------------------------------------------------------

WIN_W, WIN_H = 1160, 760
BOARD_PX = 680
BOARD_X, BOARD_Y = 32, 40
PANEL_X = BOARD_X + BOARD_PX + 24
PANEL_W = WIN_W - PANEL_X - 24

BG = (18, 19, 28)
BG2 = (26, 27, 40)
PANEL_BG = (30, 31, 46)
LIGHT_SQ = (240, 217, 181)
DARK_SQ = (181, 136, 99)
LIGHT_SQ_HOVER = (245, 228, 195)
DARK_SQ_HOVER = (193, 148, 110)
BORDER = (16, 16, 24)
TEXT = (235, 235, 245)
MUTED = (150, 152, 175)
ACCENT = (129, 182, 255)
GREEN = (110, 200, 130)
YELLOW = (240, 200, 90)
RED = (235, 90, 90)

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
        self._pick_font(int(square * 0.78))

    def _pick_font(self, size: int) -> None:
        for name in ("arialunicode", "arial", "menlo", "dejavusans", "freesans"):
            try:
                f = pygame.font.SysFont(name, size)
                # probe render
                if f.render("\u265a", True, (0, 0, 0)).get_width() > 4:
                    self.font = f
                    return
            except Exception:
                continue
        self.font = pygame.font.SysFont(None, size)

    def resize(self, square: int) -> None:
        if square != self.square:
            self.square = square
            self.cache.clear()
            self._pick_font(int(square * 0.78))

    def get(self, piece_type: int, color: bool) -> pygame.Surface:
        key = (piece_type, color)
        if key in self.cache:
            return self.cache[key]
        assert self.font is not None
        glyph = GLYPH[(piece_type, color)]
        fill = (248, 248, 250) if color == chess.WHITE else (24, 24, 30)
        outline = (30, 30, 38) if color == chess.WHITE else (238, 238, 245)
        # White pieces get a warm golden tint shadow; black a cool one.
        base = self.font.render(glyph, True, fill)
        edge = self.font.render(glyph, True, outline)
        w = base.get_width() + 6
        h = base.get_height() + 6
        surf = pygame.Surface((w, h), pygame.SRCALPHA)
        cx, cy = 3, 3
        for dx in (-2, -1, 0, 1, 2):
            for dy in (-2, -1, 0, 1, 2):
                if dx == 0 and dy == 0:
                    continue
                surf.blit(edge, (cx + dx, cy + dy))
        surf.blit(base, (cx, cy))
        # soft drop shadow
        shadow = pygame.Surface((w, h), pygame.SRCALPHA)
        shadow.blit(self.font.render(glyph, True, (0, 0, 0, 90)), (cx + 2, cy + 3))
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
        self.grades: list[coach.Grade] = []
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
        self.puzzle_rating = coach.load_rating()
        self.puzzle_status = ""  # solving | opp | solved | failed
        self.puzzle_ply = 0  # index into solution: even = your move
        self.pending_reply: tuple[chess.Move, float] | None = None
        self.daily_busy = False
        self.seen_puzzle_ids: set[str] = set()
        self.seen_puzzles: set[int] = set()  # legacy sample idxs
        self.puzzle_pool: list[dict] = coach.load_puzzle_file() or coach.sample_pool()
        # gameplay AI strength + live sparring (Stockfish on the other side)
        self.ai_level = "medium"
        self.spar_mode = False
        self.spar_target = 0  # player moves to survive
        self.spar_moves = 0
        self.spar_pending_compute = False
        self._spar_judge_pending = False
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
        x, y, w, h, gap = PANEL_X, 0, (PANEL_W - 8) // 2, 38, 8
        y = WIN_H - 56
        self.buttons = [
            Button(pygame.Rect(x, y - 48, w, h), "↺ New (N)", "new"),
            Button(pygame.Rect(x + w + 8, y - 48, w, h), "⟲ Undo (U)", "undo"),
            Button(pygame.Rect(x, y, w, h), "⇄ Flip (F)", "flip"),
            Button(pygame.Rect(x + w + 8, y, w, h), "♪ Sound: On", "sound"),
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
        if self.puzzle_mode and self.puzzle_status in ("solved", "failed"):
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

        # --- Coach grading (background, ChessTempo-style) -----------------
        if self.coach_enabled and coach_grade:
            self._request_grade(before_board, move)

        # --- Puzzle exact-match flow (Lichess-style lines) -----------------
        if self.puzzle_mode and self.puzzle is not None and not is_opponent_reply:
            self._puzzle_after_player_move(before_board, move)
        elif is_opponent_reply and self.puzzle_mode:
            # reply consumed one ply; keep solving unless line is over
            sol = (self.puzzle.get("solution") or []) if self.puzzle else []
            if self.puzzle_status == "solving" and self.puzzle_ply >= len(sol):
                self._puzzle_solved()

        # --- Sparring flow (live Stockfish opponent) -----------------------
        if self.spar_mode and coach_grade and self.puzzle is not None:
            self._spar_after_player_move(move)
        if self.spar_mode and is_opponent_reply and self.puzzle_status == "solving":
            if self.board.is_checkmate():
                self._spar_failed("Mated by spar partner")
            elif self.board.is_game_over():
                self._spar_failed("No win — draw")

    # -- coach ----------------------------------------------------------
    def _request_grade(self, before: chess.Board, played: chess.Move) -> None:
        if self.grading_busy:
            return
        self.grading_busy = True
        snapshot = before.copy()
        mv = played

        def worker() -> None:
            try:
                g = self.coach.grade(snapshot, mv, time_s=0.3, depth=14)
            except Exception:
                g = None
            self._apply_grade(g, mv)

        threading.Thread(target=worker, daemon=True).start()

    def _apply_grade(self, g: coach.Grade | None, played: chess.Move) -> None:
        self.grading_busy = False
        if g is None:
            return
        self.grades.append(g)
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
            solved = g.cp_loss <= 30
            if solved:
                self.puzzle_status = "solved"
                self.puzzle_rating = coach.update_rating(
                    self.puzzle_rating, self.puzzle["rating"], True)
            else:
                self.puzzle_status = "failed"
                self.puzzle_rating = coach.update_rating(
                    self.puzzle_rating, self.puzzle["rating"], False)
            coach.save_rating(self.puzzle_rating)
            self.seen_puzzles.add(self.puzzle_idx)
            if self.puzzle:
                self.seen_puzzle_ids.add(str(self.puzzle.get("id")))
        # sparring judgement — survive without Mistake/Blunder
        if (self.spar_mode and self._spar_judge_pending
                and self.puzzle_status == "solving"):
            self._spar_judge_pending = False
            if g.label in ("Mistake", "Blunder"):
                self._spar_failed(f"{g.label} {g.points:+d}")
            elif self.spar_moves < self.spar_target:
                self._request_spar_reply()

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
        expected_uci = sol[self.puzzle_ply] if self.puzzle_ply < len(sol) else None
        if expected_uci is None:
            return
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
            self._puzzle_failed(expected_uci, before)

    def _puzzle_solved(self) -> None:
        self.puzzle_status = "solved"
        self.pending_reply = None
        self.puzzle_rating = coach.update_rating(
            self.puzzle_rating, self.puzzle["rating"], True)
        coach.save_rating(self.puzzle_rating)
        if self.puzzle:
            self.seen_puzzle_ids.add(str(self.puzzle.get("id")))
        self.coach_score += 15
        self.coach_streak += 1
        self.coach_best_streak = max(self.coach_best_streak, self.coach_streak)
        cx = BOARD_X + BOARD_PX / 2
        self.toast = (f"Solved! +15 · ★{self.puzzle_rating}", (110, 200, 130),
                      (cx, BOARD_Y + 70), time.time())
        self.sound.promote()

    def _puzzle_failed(self, expected_uci: str, before: chess.Board) -> None:
        self.puzzle_status = "failed"
        self.pending_reply = None
        self.puzzle_rating = coach.update_rating(
            self.puzzle_rating, self.puzzle["rating"], False)
        coach.save_rating(self.puzzle_rating)
        if self.puzzle:
            self.seen_puzzle_ids.add(str(self.puzzle.get("id")))
        self.coach_streak = 0
        try:
            exp = chess.Move.from_uci(expected_uci)
            self.best_arrow = (exp.from_square, exp.to_square, time.time() + 8.0)
            try:
                san = before.san(exp)
            except Exception:
                san = expected_uci
            self.toast = (f"Miss — was {san} · ★{self.puzzle_rating}",
                          (235, 90, 90), (BOARD_X + BOARD_PX / 2, BOARD_Y + 70),
                          time.time())
        except Exception:
            pass
        self.sound.capture()

    def fire_pending_reply(self) -> None:
        if self.pending_reply is None or self.anims:
            return
        reply, due = self.pending_reply
        if time.time() < due:
            return
        self.pending_reply = None
        if self.puzzle_status == "solving" and reply in self.board.legal_moves:
            self.push_move(reply, coach_grade=False)

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
        self.toast = (f"SPAR {themes} · survive {self.spar_target} · ★{p.get('rating', '?')}",
                      (129, 182, 255), (BOARD_X + BOARD_PX / 2, BOARD_Y + 60),
                      time.time())

    def _spar_after_player_move(self, played: chess.Move) -> None:
        if self.puzzle_status != "solving":
            return
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
        self.puzzle_rating = coach.update_rating(
            self.puzzle_rating, (self.puzzle or {}).get("rating", 1200), True)
        coach.save_rating(self.puzzle_rating)
        if self.puzzle:
            self.seen_puzzle_ids.add(str(self.puzzle.get("id")))
        self.coach_score += 15
        self.coach_streak += 1
        self.coach_best_streak = max(self.coach_best_streak, self.coach_streak)
        self.toast = (f"{msg} · ★{self.puzzle_rating}", (110, 200, 130),
                      (BOARD_X + BOARD_PX / 2, BOARD_Y + 70), time.time())
        self.sound.promote()

    def _spar_failed(self, msg: str) -> None:
        self.puzzle_status = "failed"
        self.pending_reply = None
        self.spar_pending_compute = False
        self._spar_judge_pending = False
        self.puzzle_rating = coach.update_rating(
            self.puzzle_rating, (self.puzzle or {}).get("rating", 1200), False)
        coach.save_rating(self.puzzle_rating)
        if self.puzzle:
            self.seen_puzzle_ids.add(str(self.puzzle.get("id")))
        self.coach_streak = 0
        if self.board.is_checkmate() and self.board.turn != chess.WHITE:
            pass  # player got mated; board says it all
        self.toast = (f"{msg} · ★{self.puzzle_rating}", (235, 90, 90),
                      (BOARD_X + BOARD_PX / 2, BOARD_Y + 70), time.time())
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
        self.new_game()

    def _load_puzzle(self, p: dict) -> None:
        self.puzzle = p
        self.puzzle_status = "solving"
        self.puzzle_ply = 0
        self.pending_reply = None
        try:
            self.board.set_fen(p["fen"])
        except Exception:
            self.board.reset()
        self.orientation_white = self.board.turn == chess.WHITE
        self.san_history.clear()
        self.grades.clear()
        self.last_grade = None
        self.last_move = None
        self.selected = None
        self.legal_for_selected = []
        self.anims.clear()
        self.best_arrow = None
        themes = " ".join((p.get("themes") or ["tactic"])[:2])
        n = len(p.get("solution") or [])
        info = f"{themes} · {p.get('rating', '?')} · {n} moves" if n else \
            f"{themes} · {p.get('rating', '?')}"
        self.toast = (info, (235, 235, 245),
                      (BOARD_X + BOARD_PX / 2, BOARD_Y + 60), time.time())
        self._refresh_check_state()

    def _next_puzzle(self) -> None:
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
        self._load_puzzle(p)

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
                if self.grades:
                    g = self.grades.pop()
                    self.coach_score -= g.points
                    if g.points > 0 and self.coach_streak > 0:
                        self.coach_streak -= 1
            self.last_grade = self.grades[-1] if self.grades else None
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
        self._refresh_check_state()
        self.sound.move()

    # -- AI (Stockfish game opponent, selectable strength) ------------------
    def maybe_start_ai(self) -> None:
        if not self.is_ai_turn() or self.ai_thinking:
            return
        self.ai_thinking = True
        snapshot = self.board.copy()
        level = self.ai_level

        def worker() -> None:
            try:
                mv = self.coach.choose_move(snapshot, level)
            except Exception:
                mv = None
            self.ai_move = mv
            # small delay so the move doesn't feel instant + lets anim finish
            time.sleep(0.35)

        self.ai_thread = threading.Thread(target=worker, daemon=True)
        self.ai_thread.start()

    def cycle_ai_level(self) -> None:
        order = ["easy", "medium", "hard"]
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
        self.screen.fill(BG)
        # subtle background gradient circles
        self._draw_bg_glow()
        self._draw_board()
        self._draw_best_arrow()
        self._draw_pieces_and_anims()
        self._draw_panel()
        self._draw_toast()
        if self.promotion_choices:
            self._draw_promotion_dialog()
        if self.game_over_text:
            self._draw_game_over()
        if self.ai_thinking:
            self._draw_thinking()
        pygame.display.flip()

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
        # drop shadow + rounded border
        outer = pygame.Rect(BOARD_X - 12, BOARD_Y - 12, BOARD_PX + 24, BOARD_PX + 24)
        shadow = pygame.Surface((outer.w + 20, outer.h + 20), pygame.SRCALPHA)
        pygame.draw.rect(shadow, (0, 0, 0, 110), shadow.get_rect(), border_radius=18)
        self.screen.blit(shadow, (outer.x - 10, outer.y - 6))
        pygame.draw.rect(self.screen, (42, 44, 66), outer, border_radius=14)
        pygame.draw.rect(self.screen, (70, 72, 100), outer, 2, border_radius=14)

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

                # last-move highlight
                if self.last_move and real in (self.last_move.from_square, self.last_move.to_square):
                    hl = pygame.Surface((sq, sq), pygame.SRCALPHA)
                    hl.fill((255, 235, 120, 90))
                    self.screen.blit(hl, (x, y))

                # selected highlight (pulsing)
                if real == self.selected:
                    pulse = int(70 + 30 * math.sin(t * 6))
                    hl = pygame.Surface((sq, sq), pygame.SRCALPHA)
                    hl.fill((110, 200, 130, pulse + 60))
                    self.screen.blit(hl, (x, y))
                    pygame.draw.rect(self.screen, (90, 220, 140), (x + 2, y + 2, sq - 4, sq - 4), 3, border_radius=6)

                # check highlight (red radial pulse)
                if real == self.king_in_check_sq:
                    pulse = 0.5 + 0.5 * math.sin(t * 7)
                    glow = pygame.Surface((sq, sq), pygame.SRCALPHA)
                    pygame.draw.circle(glow, (235, 60, 60, int(120 + 80 * pulse)),
                                       (sq / 2, sq / 2), sq * (0.32 + 0.06 * pulse))
                    pygame.draw.circle(glow, (255, 120, 120, 200), (sq / 2, sq / 2), sq * 0.22)
                    self.screen.blit(glow, (x, y))

                # coordinates on a-file / 1st rank edges
                if file_i == 0:
                    label = str(r + 1)
                    col = DARK_SQ if light else LIGHT_SQ
                    txt = self.font_small.render(label, True, col)
                    self.screen.blit(txt, (x + 5, y + 4))
                if rank_i == 7:
                    label = chr(ord("a") + f)
                    col = DARK_SQ if light else LIGHT_SQ
                    txt = self.font_small.render(label, True, col)
                    self.screen.blit(txt, (x + sq - 16, y + sq - 20))

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

        # title
        title = self.font_title.render("♞ Chesso", True, TEXT)
        self.screen.blit(title, (PANEL_X + 18, BOARD_Y + 4))
        sub = self.font_small.render("pygame · python-chess", True, MUTED)
        self.screen.blit(sub, (PANEL_X + 20, BOARD_Y + 38))

        # turn banner
        white_to_move = self.board.turn == chess.WHITE
        banner = pygame.Rect(PANEL_X + 14, BOARD_Y + 62, PANEL_W - 28, 52)
        pygame.draw.rect(self.screen, (38, 40, 58), banner, border_radius=10)
        dot_c = (245, 245, 245) if white_to_move else (15, 15, 20)
        pygame.draw.circle(self.screen, dot_c, (banner.x + 26, banner.y + 26), 13)
        pygame.draw.circle(self.screen, (120, 120, 140), (banner.x + 26, banner.y + 26), 13, 2)
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
            mode_label += f" · {coach.EngineManager.AI_LEVELS[self.ai_level]['label']}"
        if self.spar_mode:
            mode_label = f"Spar · ★{self.puzzle_rating}"
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
        label = {  # next mode hint
            "2P": "🤖 vs AI (A)",
            "AI_BLACK": "👥 2P (A)",
            "AI_WHITE": "🤖 AI:W (A)",
        }[self.mode]
        # cycle 2P -> AI_BLACK -> AI_WHITE -> 2P
        tx = self.font_ui.render(label, True, (235, 242, 255))
        self.screen.blit(tx, (ab.x + 14, ab.y + 8))
        hov2 = lb.collidepoint(mx, my)
        pygame.draw.rect(self.screen, (52, 90, 150) if hov2 else (46, 78, 132), lb, border_radius=9)
        lv = coach.EngineManager.AI_LEVELS[self.ai_level]
        tx2 = self.font_ui.render(f"{lv['label']} (G)", True, (235, 242, 255))
        self.screen.blit(tx2, (lb.x + (lb.w - tx2.get_width()) / 2, lb.y + 8))

        # captured pieces
        wcaps, bcaps, mat = self.captured_and_material()
        cy = BOARD_Y + 172
        self.screen.blit(self.font_small.render("CAPTURED", True, MUTED), (PANEL_X + 16, cy))
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

        # move list
        ly = cy + 78
        self.screen.blit(self.font_small.render("MOVES  (scroll with wheel)", True, MUTED), (PANEL_X + 16, ly))
        list_rect = pygame.Rect(PANEL_X + 14, ly + 20, PANEL_W - 28, 170)
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
            hint = self.font_moves.render("1. e4 …", True, (90, 92, 115))
            self.screen.blit(hint, (list_rect.x + 12, y0))
        self.screen.set_clip(None)

        # --- Coach box (ChessTempo-style) --------------------------------
        co_y = list_rect.bottom + 10
        co_rect = pygame.Rect(PANEL_X + 14, co_y, PANEL_W - 28, 108)
        pygame.draw.rect(self.screen, (22, 23, 36), co_rect, border_radius=10)
        pygame.draw.rect(self.screen, (62, 64, 92), co_rect, 1, border_radius=10)
        backend = self.coach.backend if hasattr(self, "coach") else "local"
        head = f"COACH · {backend} · Score {self.coach_score} · 🔥{self.coach_streak}"
        if self.puzzle_mode and self.puzzle:
            themes = " ".join((self.puzzle.get("themes") or ["tactic"])[:2])
            sol = self.puzzle.get("solution") or []
            total = (len(sol) + 1) // 2
            done = min(total, (self.puzzle_ply + 1) // 2)
            head = (f"{themes} · ★{self.puzzle.get('rating', '?')} "
                    f"· you ★{self.puzzle_rating} · {done}/{total} "
                    f"· {self.puzzle_status}")
        elif self.spar_mode and self.puzzle:
            themes = " ".join((self.puzzle.get("themes") or ["tactic"])[:2])
            head = (f"SPAR {themes} · ★{self.puzzle.get('rating', '?')} "
                    f"· you ★{self.puzzle_rating} · "
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
            (self.coach_button, f"{'On' if self.coach_enabled else 'Off'}(C)"),
            (self.hint_button, "Hint(H)"),
            (self.puzzle_button,
             "Next▸" if self.puzzle_mode else "Puzz(P)"),
            (self.spar_button,
             "Next▸" if self.spar_mode else "Spar(S)"),
        ):
            hov = rect.collidepoint(mx, my)
            pygame.draw.rect(self.screen, (60, 63, 90) if hov else (46, 48, 70),
                             rect, border_radius=7)
            tx = self.font_small.render(lab, True, TEXT)
            self.screen.blit(tx, (rect.x + (rect.w - tx.get_width()) / 2, rect.y + 8))

        # buttons
        for b in self.buttons:
            if b.action == "sound":
                b.label = f"♪ Sound: {'On' if self.sound.enabled else 'Off'}"
            hov = b.rect.collidepoint(mx, my)
            col = (60, 63, 90) if hov else (46, 48, 70)
            pygame.draw.rect(self.screen, col, b.rect, border_radius=9)
            pygame.draw.rect(self.screen, (80, 83, 115), b.rect, 1, border_radius=9)
            tx = self.font_ui.render(b.label, True, TEXT)
            self.screen.blit(tx, (b.rect.x + (b.rect.w - tx.get_width()) / 2, b.rect.y + 9))

        # footer hint
        hint = self.font_small.render("N new/next · U undo · A AI · G level · P puzz · S spar · D daily", True, MUTED)
        self.screen.blit(hint, (PANEL_X + 14, WIN_H - 78))

    def _draw_captured_row(self, pieces: list[int], color: bool, x: int, y: int) -> None:
        cx = x
        for pt in pieces:
            g = GLYPH[(pt, color)]
            fill = (240, 240, 245) if color == chess.WHITE else (20, 20, 26)
            txt = self.font_glyph_small.render(g, True, fill)
            self.screen.blit(txt, (cx, y - 4))
            cx += 22

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
        pygame.draw.rect(self.screen, ACCENT, box, 2, border_radius=12)
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
        target = 170
        self.game_over_alpha = min(target, self.game_over_alpha + 3.5)
        overlay = pygame.Surface((BOARD_PX, 120), pygame.SRCALPHA)
        overlay.fill((12, 12, 22, int(self.game_over_alpha)))
        bx, by = BOARD_X, BOARD_Y + BOARD_PX // 2 - 60
        self.screen.blit(overlay, (bx, by))
        pygame.draw.rect(self.screen, YELLOW, (bx, by, BOARD_PX, 120), 2, border_radius=10)
        t1 = self.font_title.render(self.game_over_text, True, (255, 255, 255))
        t2 = self.font_ui.render(self.game_over_sub, True, MUTED)
        self.screen.blit(t1, (bx + (BOARD_PX - t1.get_width()) / 2, by + 22))
        self.screen.blit(t2, (bx + (BOARD_PX - t2.get_width()) / 2, by + 62))

    def _draw_thinking(self) -> None:
        dots = int(time.time() * 4) % 4
        txt = self.font_ui.render("AI thinking" + "." * dots, True, ACCENT)
        self.screen.blit(txt, (PANEL_X + 16, BOARD_Y + 122 + 40))

    # -- events ---------------------------------------------------------
    def cycle_mode(self) -> None:
        order = ["2P", "AI_BLACK", "AI_WHITE"]
        self.mode = order[(order.index(self.mode) + 1) % len(order)]
        self.sound.move()

    def handle_click(self, pos: tuple[int, int], button: int) -> None:
        x, y = pos
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
                self.enter_puzzle()
            else:
                self.enter_puzzle()
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
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.MOUSEMOTION:
                    self.hover_sq = self.pixel_to_square(*event.pos)
                    if self.dragging:
                        self.drag_pos = event.pos
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    if event.button == 1:
                        # maybe start drag
                        sq = self.pixel_to_square(*event.pos)
                        if (sq is not None and not self.promotion_choices
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
                        self.selected = None
                        self.legal_for_selected = []
                        self.promotion_choices = []
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
                        if self.spar_mode:
                            self.exit_spar()
                        if self.puzzle_mode:
                            self.exit_puzzle()
                        else:
                            self.enter_puzzle()
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

            # AI
            self.maybe_start_ai()
            self.poll_ai()
            # puzzle opponent auto-reply
            self.fire_pending_reply()

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
    game = ChessGame()
    game.run()


if __name__ == "__main__":
    main()
