from __future__ import annotations

import json
from pathlib import Path

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
