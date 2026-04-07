"""Simple minimax chess AI."""

from __future__ import annotations

import math

import chess


PIECE_VALUES = {
    chess.PAWN: 100,
    chess.KNIGHT: 320,
    chess.BISHOP: 330,
    chess.ROOK: 500,
    chess.QUEEN: 900,
    chess.KING: 20000,
}


class SimpleEngine:
    def __init__(self, depth: int = 2) -> None:
        self.depth = max(1, depth)

    def choose_move(self, board: chess.Board) -> chess.Move:
        legal_moves = list(board.legal_moves)
        if not legal_moves:
            raise ValueError("no_legal_move")

        maximizing = board.turn == chess.WHITE
        best_score = -math.inf if maximizing else math.inf
        best_move = legal_moves[0]

        for move in legal_moves:
            board.push(move)
            score = self._search(board, self.depth - 1, -math.inf, math.inf)
            board.pop()

            if maximizing and score > best_score:
                best_score = score
                best_move = move
            elif not maximizing and score < best_score:
                best_score = score
                best_move = move

        return best_move

    def _search(self, board: chess.Board, depth: int, alpha: float, beta: float) -> float:
        if depth == 0 or board.is_game_over(claim_draw=True):
            return self._evaluate(board)

        if board.turn == chess.WHITE:
            value = -math.inf
            for move in board.legal_moves:
                board.push(move)
                value = max(value, self._search(board, depth - 1, alpha, beta))
                board.pop()
                alpha = max(alpha, value)
                if alpha >= beta:
                    break
            return value

        value = math.inf
        for move in board.legal_moves:
            board.push(move)
            value = min(value, self._search(board, depth - 1, alpha, beta))
            board.pop()
            beta = min(beta, value)
            if alpha >= beta:
                break
        return value

    def _evaluate(self, board: chess.Board) -> float:
        outcome = board.outcome(claim_draw=True)
        if outcome is not None:
            if outcome.result() == "1-0":
                return 1_000_000
            if outcome.result() == "0-1":
                return -1_000_000
            return 0

        score = 0
        for piece_type, value in PIECE_VALUES.items():
            score += len(board.pieces(piece_type, chess.WHITE)) * value
            score -= len(board.pieces(piece_type, chess.BLACK)) * value

        # Encourage central control for basic positional play.
        for square in [chess.D4, chess.E4, chess.D5, chess.E5]:
            piece = board.piece_at(square)
            if piece is None:
                continue
            score += 15 if piece.color == chess.WHITE else -15

        return float(score)
