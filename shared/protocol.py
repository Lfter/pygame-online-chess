"""Line-delimited JSON protocol helpers."""

from __future__ import annotations

import json
from typing import Any

from shared.constants import MESSAGE_TYPES
from shared.errors import ERR_INVALID_PAYLOAD, ERR_UNKNOWN_MESSAGE, ProtocolValidationError


def make_message(message_type: str, **payload: Any) -> dict[str, Any]:
    if message_type not in MESSAGE_TYPES:
        raise ProtocolValidationError(f"{ERR_UNKNOWN_MESSAGE}:{message_type}")
    return {"type": message_type, **payload}


def encode_message(message: dict[str, Any]) -> bytes:
    if "type" not in message:
        raise ProtocolValidationError(f"{ERR_INVALID_PAYLOAD}:missing_type")
    return (json.dumps(message, ensure_ascii=False) + "\n").encode("utf-8")


def decode_message(raw_line: bytes | str) -> dict[str, Any]:
    if isinstance(raw_line, bytes):
        raw_line = raw_line.decode("utf-8")
    payload = json.loads(raw_line)
    if not isinstance(payload, dict):
        raise ProtocolValidationError(f"{ERR_INVALID_PAYLOAD}:not_object")
    message_type = payload.get("type")
    if message_type not in MESSAGE_TYPES:
        raise ProtocolValidationError(f"{ERR_UNKNOWN_MESSAGE}:{message_type}")
    return payload


def normalize_color(color: str) -> str:
    if color in {"white", "w"}:
        return "white"
    if color in {"black", "b"}:
        return "black"
    raise ProtocolValidationError(f"{ERR_INVALID_PAYLOAD}:color={color}")
