"""Theme loading with graceful fallback for missing assets."""

from __future__ import annotations

import hashlib
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

SYSTEM_UI_FONT_CANDIDATES = [
    "Hiragino Sans GB",
    "PingFang SC",
    "Microsoft YaHei",
    "Noto Sans CJK SC",
    "Noto Sans SC",
    "Arial Unicode MS",
    "Arial",
]

SYSTEM_PIECE_FONT_CANDIDATES = [
    "Apple Symbols",
    "Arial Unicode MS",
    "Noto Sans Symbols 2",
    "Noto Sans Symbols",
    "DejaVu Sans",
    "Arial",
]

BUNDLED_UI_FONT_FILES = [
    "NotoSansCJKsc-Regular.otf",
    "NotoSansSC-Regular.otf",
]

BUNDLED_PIECE_FONT_FILES = [
    "NotoSansSymbols2-Regular.ttf",
    "NotoSansSymbols-Regular.ttf",
    "NotoSansCJKsc-Regular.otf",
]

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
        "piece_white": [248, 249, 250],
        "piece_black": [26, 34, 44],
        "piece_outline": [18, 22, 28],
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

ASCII_PIECES: dict[str, str] = {
    "piece.white.king": "K",
    "piece.white.queen": "Q",
    "piece.white.rook": "R",
    "piece.white.bishop": "B",
    "piece.white.knight": "N",
    "piece.white.pawn": "P",
    "piece.black.king": "k",
    "piece.black.queen": "q",
    "piece.black.rook": "r",
    "piece.black.bishop": "b",
    "piece.black.knight": "n",
    "piece.black.pawn": "p",
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
        self.fonts_root = self.project_root / "assets" / "fonts"
        self.theme_data = self._load_theme(theme_name)
        self._sound_cache: dict[str, Any] = {}
        self._unicode_piece_supported = True

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

    def piece_style(self) -> dict[str, tuple[int, int, int]]:
        return {
            "white": self.get_color("piece_white"),
            "black": self.get_color("piece_black"),
            "outline": self.get_color("piece_outline"),
        }

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

    def _resolve_font_path(
        self,
        system_candidates: list[str],
        bundled_candidates: list[str],
    ) -> Path | None:
        if pygame is None:
            return None

        for name in system_candidates:
            matched = pygame.font.match_font(name)
            if matched and Path(matched).exists():
                return Path(matched)

        for file_name in bundled_candidates:
            path = self.fonts_root / file_name
            if path.exists():
                return path

        return None

    def _load_font(
        self,
        size: int,
        system_candidates: list[str],
        bundled_candidates: list[str],
    ) -> Any:
        if pygame is None:
            raise RuntimeError("pygame_not_available")

        if not pygame.font.get_init():
            pygame.font.init()

        resolved = self._resolve_font_path(system_candidates, bundled_candidates)
        if resolved is None:
            LOGGER.warning("No configured fonts found; using pygame default font")
            return pygame.font.Font(None, size)

        return pygame.font.Font(str(resolved), size)

    def _supports_unicode_piece_glyphs(self, font: Any) -> bool:
        if pygame is None:
            return False

        sample = ["♔", "♚", "♙", "♟", "♞", "♕"]
        metrics = font.metrics("".join(sample))
        if not metrics or any(metric is None for metric in metrics):
            return False

        signatures: set[str] = set()
        for glyph in sample:
            rendered = font.render(glyph, True, (255, 255, 255))
            raw = pygame.image.tostring(rendered, "RGBA")
            signatures.add(hashlib.sha1(raw).hexdigest())

        # Missing-glyph fallback often renders every symbol to identical tofu.
        return len(signatures) >= 4

    def load_fonts(self, ui_size: int = 24, panel_size: int = 20, piece_size: int = 52) -> tuple[Any, Any, Any]:
        ui_font = self._load_font(ui_size, SYSTEM_UI_FONT_CANDIDATES, BUNDLED_UI_FONT_FILES)
        panel_font = self._load_font(panel_size, SYSTEM_UI_FONT_CANDIDATES, BUNDLED_UI_FONT_FILES)
        piece_font = self._load_font(piece_size, SYSTEM_PIECE_FONT_CANDIDATES, BUNDLED_PIECE_FONT_FILES)
        self._unicode_piece_supported = self._supports_unicode_piece_glyphs(piece_font)
        return ui_font, panel_font, piece_font

    def unicode_piece_supported(self) -> bool:
        return self._unicode_piece_supported

    def piece_symbols(self, use_unicode: bool = True) -> dict[str, str]:
        mapping: dict[str, str] = {}
        if use_unicode:
            piece_data = self.theme_data.get("pieces", {})
            for color in ("white", "black"):
                for piece_type, piece_name in PIECE_NAME.items():
                    key = f"piece.{color}.{piece_name}"
                    symbol = piece_data.get(key, DEFAULT_THEME["pieces"][key])
                    mapping[key] = str(symbol)
                    # Backward-compatible numeric key for rendering helper.
                    mapping[f"piece.{color}.{piece_type}"] = str(symbol)
            return mapping

        for color in ("white", "black"):
            for piece_type, piece_name in PIECE_NAME.items():
                key = f"piece.{color}.{piece_name}"
                symbol = ASCII_PIECES[key]
                mapping[key] = symbol
                mapping[f"piece.{color}.{piece_type}"] = symbol
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
