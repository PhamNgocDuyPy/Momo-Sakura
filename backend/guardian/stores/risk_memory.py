"""Risk_Memory: per-session in-memory store written by Flow B (HARD) and read by Flow A."""

from __future__ import annotations

import threading
from dataclasses import dataclass
from datetime import datetime, timedelta

from guardian.providers.clock import Clock, SystemClock
from guardian.reason_codes import REGISTRY


@dataclass(frozen=True)
class RiskMemoryEntry:
    key: str
    reason_code: str
    created_at: datetime
    expires_at: datetime


def account_key(bin_code: str | None, digits: str) -> str:
    """Key for an account; ``acct:*:{digits}`` when the BIN is unknown."""
    return f"acct:{bin_code or '*'}:{digits}"


def domain_key(domain: str) -> str:
    return f"dom:{domain}"


def _priority(code: str) -> int:
    spec = REGISTRY.get(code)
    return spec.priority if spec is not None else 10**6


class RiskMemory:
    """Keyed by (session_id, key). Expired entries are ignored on read and purged lazily."""

    def __init__(self, ttl_hours: float = 24, clock: Clock | None = None) -> None:
        self._ttl = timedelta(hours=ttl_hours)
        self._clock: Clock = clock or SystemClock()
        self._lock = threading.Lock()
        self._data: dict[tuple[str, str], RiskMemoryEntry] = {}

    def write(self, session_id: str, key: str, reason_code: str) -> RiskMemoryEntry:
        """Write an entry. A repeated write keeps the higher-priority code (lower number)
        and the later expiry."""
        now = self._clock.now()
        with self._lock:
            self._purge(now)
            new = RiskMemoryEntry(key, reason_code, now, now + self._ttl)
            old = self._data.get((session_id, key))
            if old is not None:
                code = reason_code if _priority(reason_code) < _priority(old.reason_code) else old.reason_code
                new = RiskMemoryEntry(
                    key,
                    code,
                    old.created_at,
                    max(old.expires_at, new.expires_at),
                )
            self._data[(session_id, key)] = new
            return new

    def lookup(self, session_id: str, key: str) -> RiskMemoryEntry | None:
        now = self._clock.now()
        with self._lock:
            self._purge(now)
            return self._data.get((session_id, key))

    def lookup_account(
        self, session_id: str, bin_code: str | None, digits: str
    ) -> RiskMemoryEntry | None:
        """Match ``acct:{bin}:{digits}`` or ``acct:*:{digits}``; the higher-priority hit wins."""
        now = self._clock.now()
        with self._lock:
            self._purge(now)
            hits = [
                e
                for k in (account_key(bin_code, digits), account_key(None, digits))
                if (e := self._data.get((session_id, k))) is not None
            ]
        if not hits:
            return None
        return min(hits, key=lambda e: (_priority(e.reason_code), -e.expires_at.timestamp()))

    def lookup_domain(self, session_id: str, domain: str) -> RiskMemoryEntry | None:
        return self.lookup(session_id, domain_key(domain))

    def _purge(self, now: datetime) -> None:
        expired = [k for k, e in self._data.items() if e.expires_at <= now]
        for k in expired:
            del self._data[k]
