"""Error helpers for network protocol and game actions."""

from __future__ import annotations


class ProtocolValidationError(ValueError):
    """Raised when a protocol message is malformed."""


ERR_UNKNOWN_MESSAGE = "unknown_message"
ERR_INVALID_PAYLOAD = "invalid_payload"
ERR_ROOM_NOT_FOUND = "room_not_found"
ERR_ROOM_FULL = "room_full"
ERR_NOT_IN_ROOM = "not_in_room"
ERR_GAME_NOT_STARTED = "game_not_started"
ERR_NOT_YOUR_TURN = "not_your_turn"
ERR_ILLEGAL_MOVE = "illegal_move"
ERR_NOT_ALLOWED = "not_allowed"
ERR_INTERNAL = "internal_error"
