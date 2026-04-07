"""Stockfish UCI integration."""

from __future__ import annotations

from dataclasses import dataclass
import logging
import lzma
import os
import platform
from pathlib import Path
import shutil
import stat
from typing import Any

import chess
import chess.engine

LOGGER = logging.getLogger("stockfish")


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

BUNDLED_ENGINE_BASE = Path("assets") / "engines" / "stockfish"
BUNDLED_PACKAGE_MAP: dict[tuple[str, str], tuple[Path, Path]] = {
    (
        "darwin",
        "arm64",
    ): (
        Path("packages/macos-arm64/stockfish-sf18-macos-arm64.xz"),
        Path("bin/macos-arm64/stockfish"),
    ),
}


def _project_root(project_root: str | Path | None) -> Path:
    if project_root is None:
        return Path(__file__).resolve().parents[1]
    return Path(project_root)


def _normalize_machine(machine: str) -> str:
    normalized = machine.strip().lower()
    if normalized in {"aarch64", "arm64e"}:
        return "arm64"
    if normalized in {"x64", "amd64"}:
        return "x86_64"
    return normalized


def _platform_key() -> tuple[str, str]:
    return platform.system().strip().lower(), _normalize_machine(platform.machine())


def _embedded_paths(project_root: str | Path | None = None) -> tuple[Path | None, Path | None]:
    root = _project_root(project_root)
    mapping = BUNDLED_PACKAGE_MAP.get(_platform_key())
    if mapping is None:
        return None, None
    package_rel, binary_rel = mapping
    base = root / BUNDLED_ENGINE_BASE
    return base / package_rel, base / binary_rel


def _mark_executable(binary_path: Path) -> None:
    try:
        mode = binary_path.stat().st_mode
        binary_path.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    except Exception as exc:  # pragma: no cover - filesystem metadata edge cases
        LOGGER.warning("Unable to mark embedded stockfish executable: %s", exc)


def ensure_embedded_stockfish(project_root: str | Path | None = None) -> str:
    package_path, binary_path = _embedded_paths(project_root)
    if binary_path is None:
        return ""

    if binary_path.exists():
        _mark_executable(binary_path)
        return str(binary_path)

    if package_path is None or not package_path.exists():
        return ""

    binary_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = binary_path.with_suffix(f"{binary_path.suffix}.tmp")

    try:
        with lzma.open(package_path, "rb") as src, temp_path.open("wb") as dst:
            shutil.copyfileobj(src, dst)
        os.replace(temp_path, binary_path)
        _mark_executable(binary_path)
        return str(binary_path)
    except Exception as exc:
        LOGGER.warning("Failed to unpack bundled stockfish from %s: %s", package_path, exc)
        try:
            temp_path.unlink(missing_ok=True)
        except Exception:
            pass
        return ""


def detect_stockfish_path(configured_path: str, project_root: str | Path | None = None) -> str:
    configured = configured_path.strip()
    if configured:
        candidate = Path(configured).expanduser()
        if candidate.exists():
            return str(candidate)

    embedded = ensure_embedded_stockfish(project_root)
    if embedded:
        return embedded

    from_path = shutil.which("stockfish")
    if from_path:
        return from_path

    from_path_exe = shutil.which("stockfish.exe")
    if from_path_exe:
        return from_path_exe

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
