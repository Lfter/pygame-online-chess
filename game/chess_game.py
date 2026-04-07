"""High-level chess game wrapper built on top of python-chess."""

from __future__ import annotations

from dataclasses import dataclass
import uuid

import chess

from game.clock import ChessClock, TimeControl
from game.pgn_utils import board_to_pgn, pgn_to_board
from shared.types import GameStateDTO


TERMINATION_REASON = {
    chess.Termination.CHECKMATE: "checkmate",
    chess.Termination.STALEMATE: "stalemate",
    chess.Termination.INSUFFICIENT_MATERIAL: "insufficient_material",
    chess.Termination.SEVENTYFIVE_MOVES: "seventy_five_moves",
    chess.Termination.FIVEFOLD_REPETITION: "fivefold_repetition",
    chess.Termination.FIFTY_MOVES: "fifty_moves",
    chess.Termination.THREEFOLD_REPETITION: "threefold_repetition",
    chess.Termination.VARIANT_LOSS: "variant_loss",
    chess.Termination.VARIANT_WIN: "variant_win",
    chess.Termination.VARIANT_DRAW: "variant_draw",
}


@dataclass(slots=True)
class MoveResult:
    ok: bool
    reason: str | None = None
    move_uci: str | None = None


class ChessGame:
    def __init__(self, game_id: str | None = None) -> None:
        self.game_id = game_id or uuid.uuid4().hex[:12]
        self.board = chess.Board()
        self.clock: ChessClock | None = None
        self.forced_result: str | None = None
        self.forced_reason: str | None = None

    @property
    def turn(self) -> str:
        return "white" if self.board.turn == chess.WHITE else "black"

    def set_time_control(self, base_seconds: int, increment_seconds: int) -> None:
        self.clock = ChessClock(TimeControl(base_seconds, increment_seconds))
        self.clock.start(self.turn)

    def _autofix_promotion(self, move_uci: str) -> str:
        if len(move_uci) != 4:
            return move_uci
        from_sq = chess.parse_square(move_uci[:2])
        to_sq = chess.parse_square(move_uci[2:4])
        piece = self.board.piece_at(from_sq)
        if piece is None or piece.piece_type != chess.PAWN:
            return move_uci
        if chess.square_rank(to_sq) in {0, 7}:
            return move_uci + "q"
        return move_uci

    def apply_move(self, move_uci: str) -> MoveResult:
        if self.is_game_over():
            return MoveResult(ok=False, reason="game_over")

        try:
            normalized = self._autofix_promotion(move_uci.strip().lower())
            move = chess.Move.from_uci(normalized)
        except Exception:
            return MoveResult(ok=False, reason="invalid_uci")

        if move not in self.board.legal_moves:
            return MoveResult(ok=False, reason="illegal_move")

        moved_color = self.turn
        self.board.push(move)

        if self.clock is not None:
            timed_out = self.clock.switch_turn(moved_color)
            if timed_out is not None:
                winner = "black" if timed_out == "white" else "white"
                self.forced_result = "1-0" if winner == "white" else "0-1"
                self.forced_reason = "timeout"

        return MoveResult(ok=True, move_uci=move.uci())

    def undo_last(self, plies: int = 1) -> bool:
        if plies <= 0 or len(self.board.move_stack) < plies:
            return False
        for _ in range(plies):
            self.board.pop()
        self.forced_result = None
        self.forced_reason = None
        if self.clock is not None:
            self.clock.start(self.turn)
        return True

    def force_result(self, result: str, reason: str) -> None:
        self.forced_result = result
        self.forced_reason = reason

    def export_pgn(self) -> str:
        return board_to_pgn(self.board)

    def import_pgn(self, pgn_text: str) -> None:
        self.board = pgn_to_board(pgn_text)
        self.forced_result = None
        self.forced_reason = None
        if self.clock is not None:
            self.clock.start(self.turn)

    def legal_moves(self) -> list[str]:
        return [move.uci() for move in self.board.legal_moves]

    def is_game_over(self) -> bool:
        if self.forced_result is not None:
            return True
        return self.board.is_game_over(claim_draw=True)

    def game_result(self) -> tuple[str | None, str | None]:
        if self.forced_result is not None:
            return self.forced_result, self.forced_reason

        outcome = self.board.outcome(claim_draw=True)
        if outcome is None:
            return None, None
        reason = TERMINATION_REASON.get(outcome.termination, outcome.termination.name.lower())
        return outcome.result(), reason

    def tick_clock(self) -> tuple[str | None, str | None]:
        if self.clock is None or self.forced_result is not None:
            return self.forced_result, self.forced_reason

        timed_out = self.clock.tick()
        if timed_out is None:
            return self.game_result()

        winner = "black" if timed_out == "white" else "white"
        self.forced_result = "1-0" if winner == "white" else "0-1"
        self.forced_reason = "timeout"
        return self.forced_result, self.forced_reason

    def snapshot(self, room_id: str) -> GameStateDTO:
        result, reason = self.tick_clock()
        return GameStateDTO(
            game_id=self.game_id,
            room_id=room_id,
            fen=self.board.fen(),
            pgn=self.export_pgn(),
            turn=self.turn,
            legal_moves=self.legal_moves(),
            clock=self.clock.snapshot() if self.clock is not None else None,
            result=result,
            reason=reason,
        )
