"""Chess clock implementation with increment support."""

from __future__ import annotations

from dataclasses import dataclass
import time

from shared.types import ClockDTO


@dataclass(slots=True)
class TimeControl:
    base_seconds: int
    increment_seconds: int = 0


class ChessClock:
    def __init__(self, time_control: TimeControl) -> None:
        self.base_ms = int(time_control.base_seconds * 1000)
        self.increment_ms = int(time_control.increment_seconds * 1000)
        self.white_ms = self.base_ms
        self.black_ms = self.base_ms
        self.running_for: str | None = None
        self._last_tick: float | None = None

    def start(self, turn: str) -> None:
        self.running_for = turn
        self._last_tick = time.monotonic()

    def _consume_elapsed(self) -> str | None:
        if self.running_for is None or self._last_tick is None:
            return None
        now = time.monotonic()
        elapsed_ms = int((now - self._last_tick) * 1000)
        self._last_tick = now
        if elapsed_ms <= 0:
            return None

        if self.running_for == "white":
            self.white_ms -= elapsed_ms
            if self.white_ms <= 0:
                self.white_ms = 0
                return "white"
        else:
            self.black_ms -= elapsed_ms
            if self.black_ms <= 0:
                self.black_ms = 0
                return "black"
        return None

    def tick(self) -> str | None:
        return self._consume_elapsed()

    def switch_turn(self, moved_color: str) -> str | None:
        timed_out = self._consume_elapsed()
        if timed_out is not None:
            return timed_out

        if moved_color == "white":
            self.white_ms += self.increment_ms
            next_turn = "black"
        else:
            self.black_ms += self.increment_ms
            next_turn = "white"

        self.running_for = next_turn
        self._last_tick = time.monotonic()
        return None

    def snapshot(self) -> ClockDTO:
        self._consume_elapsed()
        return ClockDTO(
            white_ms=max(0, int(self.white_ms)),
            black_ms=max(0, int(self.black_ms)),
            increment_ms=self.increment_ms,
            running_for=self.running_for,
        )
