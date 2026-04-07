from __future__ import annotations

import lzma
import os
from pathlib import Path

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


def test_stockfish_mode_manual_fallback_raises_when_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("ai.stockfish_engine.detect_stockfish_path", lambda *_args, **_kwargs: "")
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


def test_stockfish_mode_auto_fallback_to_simple_ai(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("ai.stockfish_engine.detect_stockfish_path", lambda *_args, **_kwargs: "")
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


def test_detect_stockfish_path_respects_invalid_manual_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("ai.stockfish_engine.shutil.which", lambda _: None)
    assert detect_stockfish_path("/tmp/not-exists-stockfish", project_root=tmp_path) == ""


def test_detect_stockfish_path_uses_path_lookup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("ai.stockfish_engine.shutil.which", lambda _: "/mock/bin/stockfish")
    assert detect_stockfish_path("", project_root=tmp_path) == "/mock/bin/stockfish"


def test_detect_stockfish_path_extracts_embedded_binary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    package_dir = tmp_path / "assets" / "engines" / "stockfish" / "packages" / "macos-arm64"
    package_dir.mkdir(parents=True)
    archive_path = package_dir / "stockfish-sf18-macos-arm64.xz"
    payload = b"#!/bin/sh\necho stockfish\n"
    with lzma.open(archive_path, "wb") as handle:
        handle.write(payload)

    monkeypatch.setattr("ai.stockfish_engine.platform.system", lambda: "Darwin")
    monkeypatch.setattr("ai.stockfish_engine.platform.machine", lambda: "arm64")
    monkeypatch.setattr("ai.stockfish_engine.shutil.which", lambda _: None)

    detected = detect_stockfish_path("", project_root=tmp_path)
    expected = tmp_path / "assets" / "engines" / "stockfish" / "bin" / "macos-arm64" / "stockfish"

    assert detected == str(expected)
    assert expected.read_bytes() == payload
    assert os.access(expected, os.X_OK)
