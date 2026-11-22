"""Clock abstractions. SystemClock for TTLs, SandboxClock for wallet data and sandbox-dated features."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Protocol, runtime_checkable


@runtime_checkable
class Clock(Protocol):
    def now(self) -> datetime: ...


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(timezone.utc)


class SandboxClock:
    """Fixed clock at SANDBOX_NOW (ISO 8601 with offset, e.g. 2026-11-30T20:00:00+07:00)."""

    def __init__(self, sandbox_now: str) -> None:
        parsed = datetime.fromisoformat(sandbox_now)
        if parsed.tzinfo is None:
            raise ValueError("SANDBOX_NOW must include a UTC offset")
        self._now = parsed

    def now(self) -> datetime:
        return self._now
