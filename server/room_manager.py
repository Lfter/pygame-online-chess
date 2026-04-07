"""Room management and command handling for online play."""

from __future__ import annotations

import asyncio
import random
import string
import uuid
from typing import Any

from game.chess_game import ChessGame
from server.models import Room, RoomPlayer, Session
from shared.constants import MAX_ROOM_ID_RETRY, ROOM_ID_LENGTH
from shared.errors import (
    ERR_GAME_NOT_STARTED,
    ERR_ILLEGAL_MOVE,
    ERR_INTERNAL,
    ERR_NOT_ALLOWED,
    ERR_NOT_IN_ROOM,
    ERR_NOT_YOUR_TURN,
    ERR_ROOM_FULL,
    ERR_ROOM_NOT_FOUND,
)
from shared.protocol import encode_message, make_message


class RoomManager:
    def __init__(self) -> None:
        self.rooms: dict[str, Room] = {}
        self.player_index: dict[str, tuple[str, str]] = {}
        self._lock = asyncio.Lock()
        self._clock_tasks: dict[str, asyncio.Task[Any]] = {}

    def new_session(self, writer: asyncio.StreamWriter) -> Session:
        return Session(player_id=uuid.uuid4().hex[:12], writer=writer)

    async def _send(self, writer: asyncio.StreamWriter | None, message: dict[str, Any]) -> None:
        if writer is None:
            return
        try:
            writer.write(encode_message(message))
            await writer.drain()
        except Exception:
            return

    async def _send_error(self, session: Session, code: str, detail: str = "") -> None:
        await self._send(session.writer, make_message("error", code=code, detail=detail))

    def _make_room_id(self) -> str:
        alphabet = string.ascii_uppercase + string.digits
        for _ in range(MAX_ROOM_ID_RETRY):
            candidate = "".join(random.choice(alphabet) for _ in range(ROOM_ID_LENGTH))
            if candidate not in self.rooms:
                return candidate
        raise RuntimeError("failed_to_allocate_room_id")

    def _connected_writers(self, room: Room) -> list[asyncio.StreamWriter]:
        writers: list[asyncio.StreamWriter] = []
        for player in room.players.values():
            if player is None or not player.connected or player.writer is None:
                continue
            writers.append(player.writer)
        return writers

    async def _broadcast(self, room: Room, message: dict[str, Any]) -> None:
        for writer in self._connected_writers(room):
            await self._send(writer, message)

    async def _broadcast_room_state(self, room: Room) -> None:
        await self._broadcast(room, make_message("room_state", **room.to_payload()))

    def _room_for_session(self, session: Session) -> Room | None:
        if session.room_id is None:
            return None
        return self.rooms.get(session.room_id)

    async def handle_hello(self, session: Session, payload: dict[str, Any]) -> None:
        resume_id = str(payload.get("player_id", "")).strip()
        requested_name = str(payload.get("name", "玩家")).strip() or "玩家"

        async with self._lock:
            resumed = False
            if resume_id and resume_id in self.player_index:
                room_id, color = self.player_index[resume_id]
                room = self.rooms.get(room_id)
                if room is not None:
                    slot = room.players.get(color)
                    if slot is not None and slot.player_id == resume_id:
                        slot.connected = True
                        slot.writer = session.writer
                        session.player_id = slot.player_id
                        session.name = slot.name
                        session.room_id = room_id
                        session.color = color
                        resumed = True

            if not resumed:
                session.name = requested_name

            room = self._room_for_session(session)

        await self._send(
            session.writer,
            make_message(
                "hello",
                player_id=session.player_id,
                resumed=bool(session.room_id),
                name=session.name,
            ),
        )

        if room is not None:
            await self._broadcast_room_state(room)

    async def create_room(self, session: Session, payload: dict[str, Any]) -> None:
        async with self._lock:
            if session.room_id is not None:
                await self._send_error(session, ERR_NOT_ALLOWED, "already_in_room")
                return

            try:
                room_id = self._make_room_id()
            except RuntimeError:
                await self._send_error(session, ERR_INTERNAL, "room_id_allocation_failed")
                return

            base_seconds = int(payload.get("base_seconds", 300))
            increment_seconds = int(payload.get("increment_seconds", 0))
            room = Room(
                room_id=room_id,
                host_player_id=session.player_id,
                base_seconds=max(1, base_seconds),
                increment_seconds=max(0, increment_seconds),
            )

            host = RoomPlayer(
                player_id=session.player_id,
                name=session.name,
                color="white",
                writer=session.writer,
                connected=True,
            )
            room.players["white"] = host
            self.rooms[room_id] = room
            self.player_index[session.player_id] = (room_id, "white")
            session.room_id = room_id
            session.color = "white"

        await self._broadcast_room_state(room)

    async def join_room(self, session: Session, payload: dict[str, Any]) -> None:
        target_room_id = str(payload.get("room_id", "")).strip().upper()

        async with self._lock:
            if session.room_id is not None:
                await self._send_error(session, ERR_NOT_ALLOWED, "already_in_room")
                return

            room: Room | None = None
            if target_room_id:
                room = self.rooms.get(target_room_id)
            else:
                for candidate in self.rooms.values():
                    if candidate.status == "waiting" and candidate.players["black"] is None:
                        room = candidate
                        break

            if room is None:
                await self._send_error(session, ERR_ROOM_NOT_FOUND)
                return

            if room.players["black"] is not None:
                await self._send_error(session, ERR_ROOM_FULL)
                return

            guest = RoomPlayer(
                player_id=session.player_id,
                name=session.name,
                color="black",
                writer=session.writer,
                connected=True,
            )
            room.players["black"] = guest
            self.player_index[session.player_id] = (room.room_id, "black")
            session.room_id = room.room_id
            session.color = "black"

        await self._broadcast_room_state(room)

    async def start_game(self, session: Session, payload: dict[str, Any]) -> None:
        async with self._lock:
            room = self._room_for_session(session)
            if room is None:
                await self._send_error(session, ERR_NOT_IN_ROOM)
                return
            if not room.has_two_players():
                await self._send_error(session, ERR_NOT_ALLOWED, "missing_player")
                return

            base_seconds = int(payload.get("base_seconds", room.base_seconds))
            increment_seconds = int(payload.get("increment_seconds", room.increment_seconds))
            room.base_seconds = max(1, base_seconds)
            room.increment_seconds = max(0, increment_seconds)

            room.game = ChessGame()
            room.game.set_time_control(room.base_seconds, room.increment_seconds)
            room.pending_draw_by = None
            room.pending_undo_by = None
            room.game_over_announced = False
            room.status = "active"
            state = room.game.snapshot(room.room_id).to_dict()

            if room.room_id not in self._clock_tasks or self._clock_tasks[room.room_id].done():
                self._clock_tasks[room.room_id] = asyncio.create_task(self._clock_loop(room.room_id))

        await self._broadcast(room, make_message("start_game", room_id=room.room_id, game_state=state))
        await self._broadcast_room_state(room)

    async def apply_move(self, session: Session, payload: dict[str, Any]) -> None:
        move_uci = str(payload.get("move", "")).strip().lower()
        if not move_uci:
            await self._send_error(session, ERR_ILLEGAL_MOVE, "empty_move")
            return

        async with self._lock:
            room = self._room_for_session(session)
            if room is None:
                await self._send_error(session, ERR_NOT_IN_ROOM)
                return
            if room.game is None:
                await self._send_error(session, ERR_GAME_NOT_STARTED)
                return
            if session.color != room.game.turn:
                await self._send_error(session, ERR_NOT_YOUR_TURN)
                return

            result = room.game.apply_move(move_uci)
            if not result.ok:
                await self._send_error(session, ERR_ILLEGAL_MOVE, result.reason or "")
                return

            room.pending_draw_by = None
            room.pending_undo_by = None
            state = room.game.snapshot(room.room_id).to_dict()
            is_over = state.get("result") is not None
            if is_over:
                room.status = "finished"
                room.game_over_announced = True

        await self._broadcast(
            room,
            make_message(
                "move_result",
                room_id=room.room_id,
                move=result.move_uci,
                game_state=state,
            ),
        )

        if is_over:
            await self._broadcast(
                room,
                make_message(
                    "game_over",
                    room_id=room.room_id,
                    result=state.get("result"),
                    reason=state.get("reason"),
                    game_state=state,
                ),
            )

    async def undo_request(self, session: Session) -> None:
        async with self._lock:
            room = self._room_for_session(session)
            if room is None or room.game is None:
                await self._send_error(session, ERR_GAME_NOT_STARTED)
                return

            opponent_color = "black" if session.color == "white" else "white"
            opponent = room.players.get(opponent_color)
            if opponent is None:
                await self._send_error(session, ERR_NOT_ALLOWED, "opponent_missing")
                return

            room.pending_undo_by = session.player_id
            opponent_writer = opponent.writer

        await self._send(
            opponent_writer,
            make_message("undo_request", room_id=room.room_id, requester=session.player_id),
        )

    async def undo_response(self, session: Session, payload: dict[str, Any]) -> None:
        accepted = bool(payload.get("accepted", False))

        async with self._lock:
            room = self._room_for_session(session)
            if room is None or room.game is None:
                await self._send_error(session, ERR_GAME_NOT_STARTED)
                return
            requester_id = room.pending_undo_by
            if requester_id is None:
                await self._send_error(session, ERR_NOT_ALLOWED, "no_pending_undo")
                return

            state: dict[str, Any] | None = None
            if accepted:
                if not room.game.undo_last(1):
                    await self._send_error(session, ERR_NOT_ALLOWED, "undo_failed")
                    return
                room.status = "active"
                room.game_over_announced = False
                state = room.game.snapshot(room.room_id).to_dict()

            room.pending_undo_by = None

        await self._broadcast(
            room,
            make_message(
                "undo_response",
                room_id=room.room_id,
                requester=requester_id,
                accepted=accepted,
                game_state=state,
            ),
        )

    async def offer_draw(self, session: Session) -> None:
        async with self._lock:
            room = self._room_for_session(session)
            if room is None or room.game is None:
                await self._send_error(session, ERR_GAME_NOT_STARTED)
                return

            opponent_color = "black" if session.color == "white" else "white"
            opponent = room.players.get(opponent_color)
            if opponent is None:
                await self._send_error(session, ERR_NOT_ALLOWED, "opponent_missing")
                return

            room.pending_draw_by = session.player_id
            opponent_writer = opponent.writer

        await self._send(
            opponent_writer,
            make_message("offer_draw", room_id=room.room_id, requester=session.player_id),
        )

    async def draw_response(self, session: Session, payload: dict[str, Any]) -> None:
        accepted = bool(payload.get("accepted", False))

        async with self._lock:
            room = self._room_for_session(session)
            if room is None or room.game is None:
                await self._send_error(session, ERR_GAME_NOT_STARTED)
                return

            requester_id = room.pending_draw_by
            if requester_id is None:
                await self._send_error(session, ERR_NOT_ALLOWED, "no_pending_draw")
                return

            state: dict[str, Any] | None = None
            result = None
            reason = None
            if accepted:
                room.game.force_result("1/2-1/2", "agreed_draw")
                room.status = "finished"
                room.game_over_announced = True
                state = room.game.snapshot(room.room_id).to_dict()
                result = state.get("result")
                reason = state.get("reason")

            room.pending_draw_by = None

        await self._broadcast(
            room,
            make_message(
                "draw_response",
                room_id=room.room_id,
                requester=requester_id,
                accepted=accepted,
                game_state=state,
            ),
        )

        if accepted:
            await self._broadcast(
                room,
                make_message(
                    "game_over",
                    room_id=room.room_id,
                    result=result,
                    reason=reason,
                    game_state=state,
                ),
            )

    async def resign(self, session: Session) -> None:
        async with self._lock:
            room = self._room_for_session(session)
            if room is None or room.game is None:
                await self._send_error(session, ERR_GAME_NOT_STARTED)
                return

            winner = "black" if session.color == "white" else "white"
            result = "1-0" if winner == "white" else "0-1"
            room.game.force_result(result, "resignation")
            room.status = "finished"
            room.game_over_announced = True
            state = room.game.snapshot(room.room_id).to_dict()

        await self._broadcast(
            room,
            make_message(
                "game_over",
                room_id=room.room_id,
                result=state.get("result"),
                reason=state.get("reason"),
                game_state=state,
            ),
        )

    async def ping(self, session: Session) -> None:
        await self._send(session.writer, make_message("pong", ts=uuid.uuid4().hex[:8]))

    async def disconnect(self, session: Session) -> None:
        async with self._lock:
            if session.room_id is None or session.color is None:
                return

            room = self.rooms.get(session.room_id)
            if room is None:
                return

            player = room.players.get(session.color)
            if player is not None and player.player_id == session.player_id:
                player.connected = False
                player.writer = None

            room_id = room.room_id
            active_writers = self._connected_writers(room)
            should_cleanup = not active_writers and room.status != "active"

        await self._broadcast_room_state(room)

        if should_cleanup:
            await self._cleanup_room(room_id)

    async def _cleanup_room(self, room_id: str) -> None:
        async with self._lock:
            room = self.rooms.pop(room_id, None)
            if room is None:
                return
            for player in room.players.values():
                if player is None:
                    continue
                self.player_index.pop(player.player_id, None)

            task = self._clock_tasks.pop(room_id, None)
            if task is not None and not task.done():
                task.cancel()

    async def _clock_loop(self, room_id: str) -> None:
        try:
            while True:
                await asyncio.sleep(0.25)

                async with self._lock:
                    room = self.rooms.get(room_id)
                    if room is None:
                        break
                    if room.game is None or room.status != "active":
                        continue

                    state = room.game.snapshot(room.room_id).to_dict()
                    result = state.get("result")
                    reason = state.get("reason")
                    writers = self._connected_writers(room)

                    if result is not None and not room.game_over_announced:
                        room.status = "finished"
                        room.game_over_announced = True
                        should_send_game_over = True
                    else:
                        should_send_game_over = False

                sync_message = make_message("clock_sync", room_id=room_id, clock=state.get("clock"))
                for writer in writers:
                    await self._send(writer, sync_message)

                if should_send_game_over:
                    game_over_msg = make_message(
                        "game_over",
                        room_id=room_id,
                        result=result,
                        reason=reason,
                        game_state=state,
                    )
                    for writer in writers:
                        await self._send(writer, game_over_msg)
                    break
        except asyncio.CancelledError:
            return

    async def shutdown(self) -> None:
        async with self._lock:
            tasks = list(self._clock_tasks.values())
            self._clock_tasks.clear()
        for task in tasks:
            task.cancel()
