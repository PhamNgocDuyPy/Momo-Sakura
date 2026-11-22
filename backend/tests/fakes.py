"""Test doubles shared across test suites."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone


class FakeClock:
    """Manually advanced clock implementing the ``Clock`` protocol."""

    def __init__(self, start: datetime | None = None) -> None:
        self._now = start or datetime(2026, 11, 30, 13, 0, tzinfo=timezone.utc)

    def now(self) -> datetime:
        return self._now

    def set(self, value: datetime) -> None:
        self._now = value

    def advance(self, seconds: float = 0, **kwargs: float) -> None:
        self._now += timedelta(seconds=seconds, **kwargs)
