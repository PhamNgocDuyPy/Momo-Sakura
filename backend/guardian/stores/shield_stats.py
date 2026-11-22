"""Per-session counters of Flow A verdicts, shown on the dashboard Shield_Card."""

from __future__ import annotations

import threading

from guardian.schemas.enums import DecisionTier

_KEYS = ("ALLOW", "SOFT_FRICTION", "HARD_HOLD")


class ShieldStats:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counts: dict[str, dict[str, int]] = {}

    def record(self, session_id: str, tier: DecisionTier) -> None:
        with self._lock:
            bucket = self._counts.setdefault(session_id, dict.fromkeys(("checks", *_KEYS), 0))
            bucket["checks"] += 1
            if tier.name in _KEYS:
                bucket[tier.name] += 1

    def get(self, session_id: str) -> dict[str, int]:
        with self._lock:
            return dict(self._counts.get(session_id) or dict.fromkeys(("checks", *_KEYS), 0))
