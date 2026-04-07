"""AI engine selection and fallback behavior."""

from __future__ import annotations

import chess

from ai.simple_engine import SimpleEngine
from ai.stockfish_engine import StockfishConfig, StockfishEngine


class AIOrchestrator:
    def __init__(
        self,
        mode: str,
        simple_depth: int,
        stockfish_path: str,
        stockfish_movetime_ms: int,
        manual_fallback: bool,
    ) -> None:
        self.mode = mode
        self.simple = SimpleEngine(depth=simple_depth)
        self.stockfish = StockfishEngine(
            StockfishConfig(path=stockfish_path, movetime_ms=stockfish_movetime_ms)
        )
        self.manual_fallback = manual_fallback

    def choose_move(self, board: chess.Board) -> chess.Move:
        if self.mode == "simple":
            return self.simple.choose_move(board)

        if self.mode == "stockfish":
            if self.stockfish.is_available():
                return self.stockfish.choose_move(board)
            if self.manual_fallback:
                raise FileNotFoundError("stockfish_missing_manual_fallback")
            return self.simple.choose_move(board)

        # auto mode: prefer Stockfish and fallback to simple engine.
        if self.stockfish.is_available():
            return self.stockfish.choose_move(board)
        return self.simple.choose_move(board)

    def close(self) -> None:
        self.stockfish.close()
