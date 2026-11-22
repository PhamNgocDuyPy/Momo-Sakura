"""VerdictStore: verdict_id -> VerdictRecord (24 h), used by fast-unblock, context, commit."""

from __future__ import annotations

import secrets
import threading
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta
from typing import Any

from guardian.providers.clock import Clock, SystemClock
from guardian.schemas.enums import DecisionTier

TTL = timedelta(hours=24)


@dataclass(frozen=True)
class VerdictTx:
    bin: str | None = None
    account: str | None = None
    amount: int | None = None


@dataclass(frozen=True)
class VerdictRecord:
    verdict_id: str
    session_id: str
    channel: str
    tier: DecisionTier
    floors: Any  # FloorSet snapshot
    tx: VerdictTx
    created_at: datetime
    qr_payload: str | None = None
    cooldown_completed: bool = False
    extra: dict[str, Any] = field(default_factory=dict)


class VerdictStore:
    def __init__(self, clock: Clock | None = None) -> None:
        self._clock: Clock = clock or SystemClock()
        self._lock = threading.Lock()
        self._data: dict[str, VerdictRecord] = {}

    def put(
        self,
        *,
        session_id: str,
        channel: str,
        tier: DecisionTier,
        floors: Any,
        tx: VerdictTx | None = None,
        qr_payload: str | None = None,
        verdict_id: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> VerdictRecord:
        now = self._clock.now()
        record = VerdictRecord(
            verdict_id=verdict_id or f"vd_{secrets.token_hex(8)}",
            session_id=session_id,
            channel=channel,
            tier=tier,
            floors=floors,
            tx=tx or VerdictTx(),
            created_at=now,
            qr_payload=qr_payload,
            extra=dict(extra or {}),
        )
        with self._lock:
            self._purge(now)
            self._data[record.verdict_id] = record
        return record

    def get(self, verdict_id: str, session_id: str | None = None) -> VerdictRecord | None:
        """Return the record, or None when missing, expired or owned by another session."""
        now = self._clock.now()
        with self._lock:
            self._purge(now)
            rec = self._data.get(verdict_id)
        if rec is None or (session_id is not None and rec.session_id != session_id):
            return None
        return rec

    def update(self, verdict_id: str, **changes: Any) -> VerdictRecord | None:
        with self._lock:
            rec = self._data.get(verdict_id)
            if rec is None:
                return None
            rec = replace(rec, **changes)
            self._data[verdict_id] = rec
            return rec

    def mark_cooldown_completed(self, verdict_id: str) -> VerdictRecord | None:
        return self.update(verdict_id, cooldown_completed=True)

    def _purge(self, now: datetime) -> None:
        for k in [k for k, r in self._data.items() if now - r.created_at >= TTL]:
            del self._data[k]
