"""Non-blocking TCP client for JSON line protocol."""

from __future__ import annotations

import socket
from typing import Any

from shared.protocol import decode_message, encode_message


class NetworkClient:
    def __init__(self) -> None:
        self.sock: socket.socket | None = None
        self._buffer = b""

    @property
    def connected(self) -> bool:
        return self.sock is not None

    def connect(self, host: str, port: int, timeout: float = 5.0) -> None:
        self.close()
        sock = socket.create_connection((host, port), timeout=timeout)
        sock.setblocking(False)
        self.sock = sock
        self._buffer = b""

    def close(self) -> None:
        if self.sock is None:
            return
        try:
            self.sock.close()
        finally:
            self.sock = None
            self._buffer = b""

    def send(self, message: dict[str, Any]) -> None:
        if self.sock is None:
            raise RuntimeError("not_connected")
        self.sock.sendall(encode_message(message))

    def poll(self) -> list[dict[str, Any]]:
        if self.sock is None:
            return []

        messages: list[dict[str, Any]] = []
        while True:
            try:
                chunk = self.sock.recv(8192)
            except BlockingIOError:
                break
            if not chunk:
                self.close()
                break
            self._buffer += chunk

        if not self._buffer:
            return messages

        lines = self._buffer.split(b"\n")
        self._buffer = lines[-1]
        for raw in lines[:-1]:
            line = raw.strip()
            if not line:
                continue
            messages.append(decode_message(line))
        return messages
