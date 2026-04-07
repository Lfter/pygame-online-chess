"""DTOs shared between client and server."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class ClockDTO:
    white_ms: int
    black_ms: int
    increment_ms: int
    running_for: str | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class PlayerDTO:
    player_id: str
    name: str
    color: str
    connected: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class GameStateDTO:
    game_id: str
    room_id: str
    fen: str
    pgn: str
    turn: str
    legal_moves: list[str] = field(default_factory=list)
    clock: ClockDTO | None = None
    result: str | None = None
    reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        raw = asdict(self)
        if self.clock is not None:
            raw["clock"] = self.clock.to_dict()
        return raw
