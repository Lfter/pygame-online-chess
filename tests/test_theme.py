from __future__ import annotations

import json
from pathlib import Path

import pygame
import pytest

from client.theme import ThemeManager


def test_missing_theme_falls_back_to_default(tmp_path: Path) -> None:
    root = tmp_path
    default_dir = root / "assets" / "themes" / "default"
    default_dir.mkdir(parents=True)
    (default_dir / "theme.json").write_text(
        json.dumps(
            {
                "colors": {"background": [1, 2, 3]},
                "pieces": {"piece.white.king": "K", "piece.black.king": "k"},
            }
        ),
        encoding="utf-8",
    )

    manager = ThemeManager(root, theme_name="not-exists", audio_enabled=False)
    assert manager.background_color() == (1, 2, 3)


def test_partial_theme_inherits_default_keys(tmp_path: Path) -> None:
    root = tmp_path
    default_dir = root / "assets" / "themes" / "default"
    custom_dir = root / "assets" / "themes" / "custom"
    default_dir.mkdir(parents=True)
    custom_dir.mkdir(parents=True)

    (default_dir / "theme.json").write_text(
        json.dumps(
            {
                "colors": {
                    "background": [10, 10, 10],
                    "light_square": [20, 20, 20],
                    "dark_square": [30, 30, 30],
                    "selected": [40, 40, 40],
                    "legal_hint": [50, 50, 50],
                    "last_move": [60, 60, 60],
                    "text": [70, 70, 70],
                    "panel_bg": [80, 80, 80]
                },
                "pieces": {
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
                    "piece.black.pawn": "p"
                }
            }
        ),
        encoding="utf-8",
    )

    (custom_dir / "theme.json").write_text(
        json.dumps({"colors": {"background": [99, 98, 97]}}),
        encoding="utf-8",
    )

    manager = ThemeManager(root, theme_name="custom", audio_enabled=False)
    assert manager.background_color() == (99, 98, 97)
    assert manager.get_color("text") == (70, 70, 70)


def test_resolve_font_path_prefers_system_font(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = tmp_path
    manager = ThemeManager(root, theme_name="default", audio_enabled=False)
    system_font = root / "mock_system.ttf"
    system_font.write_bytes(b"font")

    monkeypatch.setattr("client.theme.pygame.font.match_font", lambda _: str(system_font))

    resolved = manager._resolve_font_path(
        ["Mock System Font"],
        ["NotoSansCJKsc-Regular.otf"],
    )
    assert resolved == system_font


def test_resolve_font_path_falls_back_to_bundled_font(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = tmp_path
    bundled_dir = root / "assets" / "fonts"
    bundled_dir.mkdir(parents=True)
    bundled_font = bundled_dir / "NotoSansCJKsc-Regular.otf"
    bundled_font.write_bytes(b"font")

    manager = ThemeManager(root, theme_name="default", audio_enabled=False)
    monkeypatch.setattr("client.theme.pygame.font.match_font", lambda _: None)

    resolved = manager._resolve_font_path(
        ["Mock Missing Font"],
        ["NotoSansCJKsc-Regular.otf"],
    )
    assert resolved == bundled_font


def test_piece_symbols_ascii_fallback() -> None:
    manager = ThemeManager(Path("."), theme_name="default", audio_enabled=False)
    symbols = manager.piece_symbols(use_unicode=False)
    assert symbols["piece.white.king"] == "K"
    assert symbols["piece.black.king"] == "k"
    assert symbols["piece.white.knight"] == "N"
    assert symbols["piece.black.pawn"] == "p"


class _DummySameGlyphFont:
    def metrics(self, text: str) -> list[tuple[int, int, int, int, int]]:
        return [(0, 6, 0, 11, 7) for _ in text]

    def render(self, _glyph: str, _aa: bool, _color: tuple[int, int, int]) -> pygame.Surface:
        surface = pygame.Surface((16, 16), pygame.SRCALPHA)
        surface.fill((255, 255, 255, 255))
        return surface


class _DummyDistinctGlyphFont:
    def metrics(self, text: str) -> list[tuple[int, int, int, int, int]]:
        return [(0, 10, 0, 14, 10) for _ in text]

    def render(self, glyph: str, _aa: bool, _color: tuple[int, int, int]) -> pygame.Surface:
        surface = pygame.Surface((16, 16), pygame.SRCALPHA)
        value = ord(glyph) % 251
        surface.fill((value, 255 - value, (value * 3) % 251, 255))
        return surface


def test_unicode_piece_detection_rejects_identical_tofu() -> None:
    manager = ThemeManager(Path("."), theme_name="default", audio_enabled=False)
    assert manager._supports_unicode_piece_glyphs(_DummySameGlyphFont()) is False


def test_unicode_piece_detection_accepts_distinct_glyphs() -> None:
    manager = ThemeManager(Path("."), theme_name="default", audio_enabled=False)
    assert manager._supports_unicode_piece_glyphs(_DummyDistinctGlyphFont()) is True
