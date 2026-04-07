"""Shared constants used by client and server."""

from __future__ import annotations

MESSAGE_TYPES = {
    "hello",
    "create_room",
    "join_room",
    "room_state",
    "start_game",
    "move",
    "move_result",
    "undo_request",
    "undo_response",
    "offer_draw",
    "draw_response",
    "resign",
    "game_over",
    "clock_sync",
    "error",
    "ping",
    "pong",
}

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765
MAX_ROOM_ID_RETRY = 30
ROOM_ID_LENGTH = 6
