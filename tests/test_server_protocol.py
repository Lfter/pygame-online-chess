from __future__ import annotations

import asyncio
from collections.abc import Iterable

import pytest

from server.app import ChessServer
from shared.protocol import decode_message, encode_message, make_message


async def recv_message(reader: asyncio.StreamReader, timeout: float = 2.0) -> dict:
    raw = await asyncio.wait_for(reader.readline(), timeout=timeout)
    assert raw, "connection_closed"
    return decode_message(raw)


async def recv_until(
    reader: asyncio.StreamReader,
    expected_types: Iterable[str],
    timeout: float = 3.0,
) -> dict:
    expected = set(expected_types)
    while True:
        message = await recv_message(reader, timeout=timeout)
        if message.get("type") in expected:
            return message


async def send_message(writer: asyncio.StreamWriter, message: dict) -> None:
    writer.write(encode_message(message))
    await writer.drain()


async def scenario_room_flow_reconnect_timeout() -> None:
    server = ChessServer("127.0.0.1", 0)
    try:
        await server.start()
    except PermissionError:
        pytest.skip("Socket binding is not permitted in this execution sandbox")

    reader1, writer1 = await asyncio.open_connection("127.0.0.1", server.bound_port)
    reader2, writer2 = await asyncio.open_connection("127.0.0.1", server.bound_port)

    hello1 = await recv_until(reader1, {"hello"})
    hello2 = await recv_until(reader2, {"hello"})
    player2 = hello2["player_id"]

    await send_message(writer1, make_message("hello", name="A"))
    await send_message(writer2, make_message("hello", name="B"))

    await recv_until(reader1, {"hello"})
    await recv_until(reader2, {"hello"})

    await send_message(writer1, make_message("create_room", base_seconds=1, increment_seconds=0))
    room_state_host = await recv_until(reader1, {"room_state"})
    room_id = room_state_host["room_id"]

    await send_message(writer2, make_message("join_room", room_id=room_id))
    room_state_guest = await recv_until(reader2, {"room_state"})
    assert room_state_guest["room_id"] == room_id

    await send_message(writer1, make_message("start_game", base_seconds=1, increment_seconds=0))
    await recv_until(reader1, {"start_game"})
    await recv_until(reader2, {"start_game"})

    # Illegal because black moves before white.
    await send_message(writer2, make_message("move", move="e7e5"))
    err = await recv_until(reader2, {"error"})
    assert err["code"] == "not_your_turn"

    await send_message(writer1, make_message("move", move="e2e4"))
    move_result = await recv_until(reader1, {"move_result"})
    assert move_result["move"] == "e2e4"

    # Reconnect guest with same player id.
    writer2.close()
    await writer2.wait_closed()

    reader2b, writer2b = await asyncio.open_connection("127.0.0.1", server.bound_port)
    await recv_until(reader2b, {"hello"})
    await send_message(writer2b, make_message("hello", player_id=player2, name="B"))
    resumed = await recv_until(reader2b, {"hello"})
    assert resumed.get("player_id") == player2
    assert resumed.get("resumed") is True

    # Wait timeout to trigger game_over.
    game_over = await recv_until(reader1, {"game_over"}, timeout=4.0)
    assert game_over["reason"] == "timeout"

    writer1.close()
    writer2b.close()
    await writer1.wait_closed()
    await writer2b.wait_closed()
    await server.stop()


def test_server_room_flow_reconnect_and_timeout() -> None:
    asyncio.run(scenario_room_flow_reconnect_timeout())
