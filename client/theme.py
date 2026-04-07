"""Theme loading with graceful fallback for missing assets."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import chess

from client.board_ui import UiTheme

try:
    import pygame
except Exception:  # pragma: no cover - pygame import is environment-dependent
    pygame = None  # type: ignore[assignment]


LOGGER = logging.getLogger("theme")

PIECE_NAME = {
    chess.PAWN: "pawn",
    chess.KNIGHT: "knight",
    chess.BISHOP: "bishop",
    chess.ROOK: "rook",
    chess.QUEEN: "queen",
    chess.KING: "king",
}

DEFAULT_THEME: dict[str, Any] = {
    "colors": {
        "background": [26, 34, 44],
        "light_square": [232, 235, 239],
        "dark_square": [105, 146, 165],
        "selected": [250, 181, 33],
        "legal_hint": [35, 180, 90],
        "last_move": [255, 121, 89],
        "text": [248, 249, 250],
        "panel_bg": [35, 46, 60],
    },
    "pieces": {
        "piece.white.king": "♔",
        "piece.white.queen": "♕",
        "piece.white.rook": "♖",
        "piece.white.bishop": "♗",
        "piece.white.knight": "♘",
        "piece.white.pawn": "♙",
        "piece.black.king": "♚",
        "piece.black.queen": "♛",
        "piece.black.rook": "♜",
        "piece.black.bishop": "♝",
        "piece.black.knight": "♞",
        "piece.black.pawn": "♟",
    },
    "audio": {
        "sfx.move": "sfx_move.wav",
        "sfx.capture": "sfx_capture.wav",
        "bgm.menu": "bgm_menu.wav",
    },
}


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    out = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            out[key] = _deep_merge(base[key], value)
        else:
            out[key] = value
    return out


class ThemeManager:
    def __init__(self, project_root: Path, theme_name: str = "default", audio_enabled: bool = True) -> None:
        self.project_root = project_root
        self.theme_name = theme_name
        self.audio_enabled = audio_enabled
        self.theme_data = self._load_theme(theme_name)
        self._sound_cache: dict[str, Any] = {}

    def _theme_path(self, theme_name: str) -> Path:
        return self.project_root / "assets" / "themes" / theme_name / "theme.json"

    def _load_theme(self, theme_name: str) -> dict[str, Any]:
        default_path = self._theme_path("default")
        default_data = dict(DEFAULT_THEME)
        if default_path.exists():
            try:
                default_data = _deep_merge(default_data, json.loads(default_path.read_text(encoding="utf-8")))
            except Exception as exc:
                LOGGER.warning("Failed to load default theme file: %s", exc)

        if theme_name == "default":
            return default_data

        custom_path = self._theme_path(theme_name)
        if not custom_path.exists():
            LOGGER.warning("Theme '%s' missing, fallback to default", theme_name)
            return default_data

        try:
            custom_data = json.loads(custom_path.read_text(encoding="utf-8"))
            if not isinstance(custom_data, dict):
                raise ValueError("theme_not_object")
            return _deep_merge(default_data, custom_data)
        except Exception as exc:
            LOGGER.warning("Theme '%s' invalid, fallback to default: %s", theme_name, exc)
            return default_data

    def get_color(self, key: str) -> tuple[int, int, int]:
        raw = self.theme_data.get("colors", {}).get(key, DEFAULT_THEME["colors"][key])
        if not isinstance(raw, list) or len(raw) != 3:
            raw = DEFAULT_THEME["colors"][key]
        return (int(raw[0]), int(raw[1]), int(raw[2]))

    def ui_theme(self) -> UiTheme:
        return UiTheme(
            light_square=self.get_color("light_square"),
            dark_square=self.get_color("dark_square"),
            selected=self.get_color("selected"),
            legal_hint=self.get_color("legal_hint"),
            last_move=self.get_color("last_move"),
            text=self.get_color("text"),
            panel_bg=self.get_color("panel_bg"),
        )

    def background_color(self) -> tuple[int, int, int]:
        return self.get_color("background")

    def piece_symbols(self) -> dict[str, str]:
        mapping: dict[str, str] = {}
        piece_data = self.theme_data.get("pieces", {})
        for color in ("white", "black"):
            for piece_type, piece_name in PIECE_NAME.items():
                key = f"piece.{color}.{piece_name}"
                symbol = piece_data.get(key, DEFAULT_THEME["pieces"][key])
                mapping[key] = str(symbol)
                # Backward-compatible numeric key for rendering helper.
                mapping[f"piece.{color}.{piece_type}"] = str(symbol)
        return mapping

    def _resolve_audio_path(self, key: str) -> Path | None:
        rel = self.theme_data.get("audio", {}).get(key)
        if not rel:
            rel = DEFAULT_THEME["audio"].get(key)
        if not rel:
            return None
        candidate = self.project_root / "assets" / "themes" / self.theme_name / rel
        if candidate.exists():
            return candidate
        fallback = self.project_root / "assets" / "themes" / "default" / rel
        return fallback if fallback.exists() else None

    def get_sound(self, key: str) -> Any | None:
        if not self.audio_enabled or pygame is None:
            return None
        if key in self._sound_cache:
            return self._sound_cache[key]

        if not pygame.mixer.get_init():
            return None

        sound_path = self._resolve_audio_path(key)
        if sound_path is None:
            return None

        try:
            sound = pygame.mixer.Sound(str(sound_path))
        except Exception as exc:
            LOGGER.warning("Failed to load sound %s: %s", key, exc)
            sound = None
        self._sound_cache[key] = sound
        return sound

    def play_sfx(self, key: str, volume: float = 1.0) -> None:
        sound = self.get_sound(key)
        if sound is None:
            return
        sound.set_volume(max(0.0, min(1.0, volume)))
        sound.play()
