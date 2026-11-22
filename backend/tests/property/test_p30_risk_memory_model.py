"""Property 30: Risk_Memory theo mô hình tham chiếu.

**Validates: Requirements 18.3, 18.4, 18.5, 18.6**
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from hypothesis import given

from guardian.reason_codes import REGISTRY
from guardian.stores.risk_memory import RiskMemory
from tests.property.strategies.risk_memory import risk_memory_ops

_TTL = timedelta(hours=24)


class FakeClock:
    def __init__(self) -> None:
        self.t = datetime(2026, 1, 1, tzinfo=timezone.utc)

    def now(self) -> datetime:
        return self.t


@given(risk_memory_ops())
def test_risk_memory_matches_reference_model(ops: list[tuple]) -> None:
    clock = FakeClock()
    mem = RiskMemory(ttl_hours=24, clock=clock)
    model: dict[tuple[str, str], tuple[str, datetime]] = {}  # (session, key) -> (code, expires)

    for op in ops:
        if op[0] == "advance":
            clock.t += timedelta(seconds=op[1])
        elif op[0] == "write":
            _, session, key, code = op
            now = clock.t
            model = {k: v for k, v in model.items() if v[1] > now}
            old = model.get((session, key))
            if old is not None and REGISTRY[old[0]].priority <= REGISTRY[code].priority:
                code = old[0]
            model[(session, key)] = (code, now + _TTL)
            mem.write(session, key, op[3])
        else:
            _, session, key = op
            expected = model.get((session, key))
            if expected is not None and expected[1] <= clock.t:
                expected = None
            got = mem.lookup(session, key)
            if expected is None:
                assert got is None
            else:
                assert got is not None
                assert got.reason_code == expected[0]
                assert got.expires_at == expected[1]
