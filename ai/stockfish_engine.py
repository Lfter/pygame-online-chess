"""Stockfish UCI integration."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shutil
from typing import Any

import chess
import chess.engine


@dataclass(slots=True)
class StockfishConfig:
    path: str
    movetime_ms: int = 350


COMMON_STOCKFISH_PATHS = [
    "/opt/homebrew/bin/stockfish",
    "/usr/local/bin/stockfish",
    "/opt/local/bin/stockfish",
    "/usr/bin/stockfish",
]


def detect_stockfish_path(configured_path: str) -> str:
    configured = configured_path.strip()
    if configured:
        candidate = Path(configured)
        return configured if candidate.exists() else ""

    from_path = shutil.which("stockfish")
    if from_path:
        return from_path

    for candidate in COMMON_STOCKFISH_PATHS:
        if Path(candidate).exists():
            return candidate
    return ""


class StockfishEngine:
    def __init__(self, config: StockfishConfig) -> None:
        self.config = config
        self._resolved_path = detect_stockfish_path(config.path)
        self._engine: chess.engine.SimpleEngine | None = None

    def is_available(self) -> bool:
        return bool(self._resolved_path)

    def _ensure_engine(self) -> chess.engine.SimpleEngine:
        if self._engine is None:
            if not self._resolved_path:
                raise FileNotFoundError("stockfish_not_found")
            self._engine = chess.engine.SimpleEngine.popen_uci(self._resolved_path)
        return self._engine

    def choose_move(self, board: chess.Board) -> chess.Move:
        if not self.is_available():
            raise FileNotFoundError("stockfish_not_found")

        engine = self._ensure_engine()
        result = engine.play(board, chess.engine.Limit(time=max(0.05, self.config.movetime_ms / 1000.0)))
        if result.move is None:
            raise ValueError("stockfish_no_move")
        return result.move

    def close(self) -> None:
        if self._engine is not None:
            self._engine.quit()
            self._engine = None

    def __enter__(self) -> "StockfishEngine":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()
