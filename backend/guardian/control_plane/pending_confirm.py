"""PendingConfirmStore (R2 two-step name confirmation) and ConfirmationTokens (D4). TTL 30 min."""

from __future__ import annotations

import secrets
import threading
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta
from typing import Any

from guardian.providers.clock import Clock, SystemClock

TTL = timedelta(minutes=30)


@dataclass(frozen=True)
class PendingNameConfirm:
    pending_id: str
    session_id: str
    bin: str
    account: str
    created_at: datetime
    extraction: Any = None
    floors_snapshot: Any = None
    status: str = "PENDING"
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class _Token:
    session_id: str
    bin: str
    account: str
    created_at: datetime


class PendingConfirmStore:
    def __init__(self, clock: Clock | None = None) -> None:
        self._clock: Clock = clock or SystemClock()
        self._lock = threading.Lock()
        self._pending: dict[str, PendingNameConfirm] = {}
        self._tokens: dict[str, _Token] = {}

    def create(
        self,
        session_id: str,
        bin_code: str,
        account: str,
        extraction: Any = None,
        floors_snapshot: Any = None,
    ) -> PendingNameConfirm:
        now = self._clock.now()
        rec = PendingNameConfirm(
            pending_id=f"pc_{secrets.token_hex(8)}",
            session_id=session_id,
            bin=bin_code,
            account=account,
            created_at=now,
            extraction=extraction,
            floors_snapshot=floors_snapshot,
        )
        with self._lock:
            self._purge(now)
            self._pending[rec.pending_id] = rec
        return rec

    def get(self, pending_id: str, session_id: str | None = None) -> PendingNameConfirm | None:
        now = self._clock.now()
        with self._lock:
            self._purge(now)
            rec = self._pending.get(pending_id)
        if rec is None or (session_id is not None and rec.session_id != session_id):
            return None
        return rec

    def update(self, pending_id: str, **changes: Any) -> PendingNameConfirm | None:
        """Update fields, e.g. the account digits after the user corrects them."""
        with self._lock:
            rec = self._pending.get(pending_id)
            if rec is None:
                return None
            rec = replace(rec, **changes)
            self._pending[pending_id] = rec
            return rec

    def issue_token(self, session_id: str, bin_code: str, account: str) -> str:
        now = self._clock.now()
        token = f"ct_{secrets.token_urlsafe(16)}"
        with self._lock:
            self._purge(now)
            self._tokens[token] = _Token(session_id, bin_code, account, now)
        return token

    def validate_token(
        self, token: str | None, session_id: str, bin_code: str, account: str
    ) -> bool:
        """True only when the token is live and bound to this session, BIN and account."""
        if not token:
            return False
        now = self._clock.now()
        with self._lock:
            self._purge(now)
            t = self._tokens.get(token)
        return (
            t is not None
            and t.session_id == session_id
            and t.bin == bin_code
            and t.account == account
        )

    def _purge(self, now: datetime) -> None:
        for k in [k for k, r in self._pending.items() if now - r.created_at >= TTL]:
            del self._pending[k]
        for k in [k for k, t in self._tokens.items() if now - t.created_at >= TTL]:
            del self._tokens[k]
