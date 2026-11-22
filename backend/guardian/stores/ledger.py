"""Ledger: per-session committed transfers, summed over 24 h for R5 structuring."""

from __future__ import annotations

import threading
from dataclasses import dataclass
from datetime import datetime, timedelta

from guardian.providers.clock import Clock, SystemClock

WINDOW = timedelta(hours=24)


@dataclass(frozen=True)
class LedgerEntry:
    at: datetime
    bin: str
    account: str
    amount: int


class Ledger:
    def __init__(self, clock: Clock | None = None) -> None:
        self._clock: Clock = clock or SystemClock()
        self._lock = threading.Lock()
        self._data: dict[str, list[LedgerEntry]] = {}

    def add(self, session_id: str, bin_code: str, account: str, amount: int) -> LedgerEntry:
        now = self._clock.now()
        entry = LedgerEntry(now, bin_code, account, amount)
        with self._lock:
            self._purge(session_id, now)
            self._data.setdefault(session_id, []).append(entry)
        return entry

    def total_24h(self, session_id: str) -> int:
        now = self._clock.now()
        with self._lock:
            self._purge(session_id, now)
            return sum(e.amount for e in self._data.get(session_id, []))

    def _purge(self, session_id: str, now: datetime) -> None:
        entries = self._data.get(session_id)
        if entries:
            self._data[session_id] = [e for e in entries if now - e.at < WINDOW]
