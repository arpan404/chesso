"""Chess rules and a small, explicitly unrated web opponent."""

import random

import chess

VALUES = {
    chess.PAWN: 100,
    chess.KNIGHT: 320,
    chess.BISHOP: 330,
    chess.ROOK: 500,
    chess.QUEEN: 900,
    chess.KING: 0,
}


def board_data(board):
    outcome = board.outcome(claim_draw=True)
    return {
        "fen": board.fen(),
        "pieces": {
            chess.square_name(sq): piece.symbol()
            for sq, piece in board.piece_map().items()
        },
        "legal_moves": [m.uci() for m in board.legal_moves] if outcome is None else [],
        "turn": "white" if board.turn else "black",
        "check": board.is_check(),
        "result": outcome.result() if outcome else None,
        "termination": outcome.termination.name.lower() if outcome else None,
    }


def game_board(state):
    board = chess.Board()
    for move in state["moves"]:
        board.push_uci(move)
    return board


def opponent_move(board):
    def score(position):
        if position.is_checkmate():
            return -100000
        if position.is_game_over(claim_draw=True):
            return 0
        material = sum(
            VALUES[p.piece_type] * (1 if p.color == position.turn else -1)
            for p in position.piece_map().values()
        )
        return material

    def search(position, depth, alpha, beta):
        if depth == 0 or position.is_game_over(claim_draw=True):
            return score(position)
        best = -float("inf")
        for move in sorted(position.legal_moves, key=position.is_capture, reverse=True):
            position.push(move)
            value = -search(position, depth - 1, -beta, -alpha)
            position.pop()
            best, alpha = max(best, value), max(alpha, value)
            if alpha >= beta:
                break
        return best

    best, choices = -float("inf"), []
    for move in board.legal_moves:
        board.push(move)
        value = -search(board, 1, -float("inf"), float("inf"))
        board.pop()
        if value > best:
            best, choices = value, [move]
        elif value == best:
            choices.append(move)
    return random.choice(choices)
