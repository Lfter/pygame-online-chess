"""Application settings loader and saver."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


DEFAULT_SETTINGS: dict[str, Any] = {
    "window": {"width": 1080, "height": 760, "fps": 60},
    "audio": {
        "master_volume": 0.6,
        "sfx_volume": 0.75,
        "bgm_volume": 0.35,
        "enabled": True,
    },
    "theme": {"name": "default"},
    "ai": {
        "mode": "simple",
        "simple_depth": 2,
        "stockfish_path": "",
        "stockfish_movetime_ms": 350,
        "manual_fallback": True,
    },
    "network": {"default_host": "127.0.0.1", "default_port": 8765, "room_id": ""},
    "time_control": {
        "base_seconds": 300,
        "increment_seconds": 3,
        "presets": [[180, 0], [300, 3], [600, 5], [900, 10]],
    },
}


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    output = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            output[key] = _deep_merge(base[key], value)
        else:
            output[key] = value
    return output


def load_settings(path: str | Path) -> dict[str, Any]:
    file_path = Path(path)
    if not file_path.exists():
        return dict(DEFAULT_SETTINGS)

    raw = json.loads(file_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        return dict(DEFAULT_SETTINGS)
    return _deep_merge(DEFAULT_SETTINGS, raw)


def save_settings(path: str | Path, settings: dict[str, Any]) -> None:
    file_path = Path(path)
    file_path.write_text(json.dumps(settings, ensure_ascii=False, indent=2), encoding="utf-8")
