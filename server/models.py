"""Server-side state models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
import asyncio

from game.chess_game import ChessGame


@dataclass(slots=True)
class Session:
    player_id: str
    writer: asyncio.StreamWriter
    name: str = "玩家"
    room_id: str | None = None
    color: str | None = None


@dataclass(slots=True)
class RoomPlayer:
    player_id: str
    name: str
    color: str
    writer: asyncio.StreamWriter | None
    connected: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "player_id": self.player_id,
            "name": self.name,
            "color": self.color,
            "connected": self.connected,
        }


@dataclass(slots=True)
class Room:
    room_id: str
    host_player_id: str
    base_seconds: int
    increment_seconds: int
    players: dict[str, RoomPlayer | None] = field(
        default_factory=lambda: {"white": None, "black": None}
    )
    game: ChessGame | None = None
    pending_undo_by: str | None = None
    pending_draw_by: str | None = None
    status: str = "waiting"
    game_over_announced: bool = False

    def has_two_players(self) -> bool:
        return self.players["white"] is not None and self.players["black"] is not None

    def to_payload(self) -> dict[str, Any]:
        return {
            "room_id": self.room_id,
            "status": self.status,
            "players": [
                player.to_dict() for player in self.players.values() if player is not None
            ],
            "time_control": {
                "base_seconds": self.base_seconds,
                "increment_seconds": self.increment_seconds,
            },
            "game_state": self.game.snapshot(self.room_id).to_dict() if self.game else None,
        }
