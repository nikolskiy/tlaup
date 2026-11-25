"""The injected time of the tests (design 01 T4, Time)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta


class FakeClock:
    """A clock that moves only when told: by ``advance``, or by ``sleep``, which also records the request.

    One object serves the three shapes the code takes: ``clock: Callable[[], float]`` (call it),
    ``now: Callable[[], datetime]`` (``now``) and ``sleep: Callable[[float], None]`` (``sleep``).
    """

    def __init__(self, start: datetime = datetime(2026, 11, 15, tzinfo=UTC)) -> None:
        if start.tzinfo is None or start.utcoffset() is None:
            message = "FakeClock needs an aware start time"
            raise ValueError(message)
        self._now = start.astimezone(UTC)
        self.sleeps: list[float] = []

    def __call__(self) -> float:
        """Seconds since the epoch."""
        return self._now.timestamp()

    def now(self) -> datetime:
        """The current time, aware, in UTC."""
        return self._now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.advance(seconds)

    def advance(self, seconds: float) -> None:
        if seconds < 0:
            message = "time does not go back"
            raise ValueError(message)
        self._now += timedelta(seconds=seconds)
