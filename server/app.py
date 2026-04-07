"""Async TCP relay server for online chess matches."""

from __future__ import annotations

import argparse
import asyncio
import logging
from typing import Any

from server.room_manager import RoomManager
from shared.errors import ProtocolValidationError, ERR_INVALID_PAYLOAD, ERR_UNKNOWN_MESSAGE
from shared.protocol import decode_message, make_message, encode_message


LOGGER = logging.getLogger("chess_server")


class ChessServer:
    def __init__(self, host: str, port: int) -> None:
        self.host = host
        self.port = port
        self.manager = RoomManager()
        self._server: asyncio.AbstractServer | None = None

    @property
    def bound_port(self) -> int:
        if self._server is None or not self._server.sockets:
            return self.port
        return int(self._server.sockets[0].getsockname()[1])

    async def start(self) -> None:
        self._server = await asyncio.start_server(self._handle_client, self.host, self.port)
        LOGGER.info("Server started at %s:%s", self.host, self.bound_port)

    async def stop(self) -> None:
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
        await self.manager.shutdown()

    async def serve_forever(self) -> None:
        if self._server is None:
            await self.start()
        assert self._server is not None
        async with self._server:
            await self._server.serve_forever()

    async def _safe_send(self, writer: asyncio.StreamWriter, message: dict[str, Any]) -> None:
        try:
            writer.write(encode_message(message))
            await writer.drain()
        except Exception:
            return

    async def _handle_client(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        session = self.manager.new_session(writer)
        peer_name = writer.get_extra_info("peername")
        LOGGER.info("Client connected: %s", peer_name)

        await self._safe_send(
            writer,
            make_message(
                "hello",
                player_id=session.player_id,
                resumed=False,
                name=session.name,
                welcome="send hello message to set your name or resume",
            ),
        )

        try:
            while True:
                raw_line = await reader.readline()
                if not raw_line:
                    break

                try:
                    message = decode_message(raw_line)
                except ProtocolValidationError as exc:
                    await self._safe_send(
                        writer,
                        make_message("error", code=ERR_INVALID_PAYLOAD, detail=str(exc)),
                    )
                    continue
                except Exception as exc:
                    await self._safe_send(
                        writer,
                        make_message("error", code=ERR_INVALID_PAYLOAD, detail=str(exc)),
                    )
                    continue

                msg_type = message.get("type")
                try:
                    await self._dispatch(session, message)
                except Exception as exc:  # keep server alive for other clients
                    LOGGER.exception("handler failure: %s", exc)
                    await self._safe_send(
                        writer,
                        make_message("error", code="handler_failure", detail=f"{msg_type}:{exc}"),
                    )
        finally:
            await self.manager.disconnect(session)
            writer.close()
            await writer.wait_closed()
            LOGGER.info("Client disconnected: %s", peer_name)

    async def _dispatch(self, session: Any, message: dict[str, Any]) -> None:
        msg_type = message["type"]

        if msg_type == "hello":
            await self.manager.handle_hello(session, message)
            return
        if msg_type == "create_room":
            await self.manager.create_room(session, message)
            return
        if msg_type == "join_room":
            await self.manager.join_room(session, message)
            return
        if msg_type == "start_game":
            await self.manager.start_game(session, message)
            return
        if msg_type == "move":
            await self.manager.apply_move(session, message)
            return
        if msg_type == "undo_request":
            await self.manager.undo_request(session)
            return
        if msg_type == "undo_response":
            await self.manager.undo_response(session, message)
            return
        if msg_type == "offer_draw":
            await self.manager.offer_draw(session)
            return
        if msg_type == "draw_response":
            await self.manager.draw_response(session, message)
            return
        if msg_type == "resign":
            await self.manager.resign(session)
            return
        if msg_type == "ping":
            await self.manager.ping(session)
            return

        await self._safe_send(
            session.writer,
            make_message("error", code=ERR_UNKNOWN_MESSAGE, detail=msg_type),
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Pygame online chess relay server")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--log-level", default="INFO")
    return parser.parse_args()


async def _main_async() -> None:
    args = parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    server = ChessServer(host=args.host, port=args.port)
    await server.start()
    try:
        await server.serve_forever()
    finally:
        await server.stop()


def main() -> None:
    asyncio.run(_main_async())


if __name__ == "__main__":
    main()
