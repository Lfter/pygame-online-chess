from __future__ import annotations

import chess
import pytest

from ai.factory import AIOrchestrator
from ai.simple_engine import SimpleEngine
from ai.stockfish_engine import detect_stockfish_path


def test_simple_engine_returns_legal_move() -> None:
    board = chess.Board()
    engine = SimpleEngine(depth=2)
    move = engine.choose_move(board)
    assert move in board.legal_moves


def test_stockfish_mode_manual_fallback_raises_when_missing() -> None:
    board = chess.Board()
    orchestrator = AIOrchestrator(
        mode="stockfish",
        simple_depth=2,
        stockfish_path="/tmp/not-exists-stockfish",
        stockfish_movetime_ms=200,
        manual_fallback=True,
    )
    with pytest.raises(FileNotFoundError):
        orchestrator.choose_move(board)


def test_stockfish_mode_auto_fallback_to_simple_ai() -> None:
    board = chess.Board()
    orchestrator = AIOrchestrator(
        mode="stockfish",
        simple_depth=1,
        stockfish_path="/tmp/not-exists-stockfish",
        stockfish_movetime_ms=200,
        manual_fallback=False,
    )
    move = orchestrator.choose_move(board)
    assert move in board.legal_moves


def test_detect_stockfish_path_respects_invalid_manual_path() -> None:
    assert detect_stockfish_path("/tmp/not-exists-stockfish") == ""


def test_detect_stockfish_path_uses_path_lookup(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("ai.stockfish_engine.shutil.which", lambda _: "/mock/bin/stockfish")
    assert detect_stockfish_path("") == "/mock/bin/stockfish"
