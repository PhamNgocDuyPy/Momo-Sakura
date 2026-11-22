"""Property 32: Chia hóa đơn bảo toàn tổng.

**Validates: Requirements 22.3, 22.4, 22.7**
"""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from guardian.features.bill_splitter import compute_split, split_equal
from tests.property.strategies.receipts import Receipt, receipts


@settings(max_examples=200)
@given(st.integers(0, 10**9), st.integers(1, 20))
def test_equal_split_conserves_total(total: int, n: int) -> None:
    people = [f"p{i}" for i in range(n)]
    shares = split_equal(total, people)
    assert sum(shares.values()) == total
    values = [shares[p] for p in people]
    assert max(values) - min(values) <= 1
    assert values == sorted(values, reverse=True)  # remainder goes to the first people


@settings(max_examples=200)
@given(receipts())
def test_split_conserves_receipt_total(r: Receipt) -> None:
    for mode in ("EQUAL", "BY_ITEM"):
        out = compute_split(r.items, r.total, r.participants, mode, r.assignments)  # type: ignore[arg-type]
        assert out.status == "OK"
        assert out.mismatch_vnd == 0
        assert sum(out.shares.values()) == r.total
        assert set(out.shares) == set(r.participants)
        assert all(v >= 0 for v in out.shares.values())


@settings(max_examples=200)
@given(receipts(), st.integers(1, 5_000_000), st.booleans())
def test_mismatch_returns_no_shares(r: Receipt, delta: int, over: bool) -> None:
    claimed = r.total + delta if over else max(r.total - delta, 0)
    out = compute_split(r.items, claimed, r.participants, "EQUAL", None)
    if claimed == r.total:  # clamped at zero
        assert out.status == "OK"
        return
    assert out.status == "TOTAL_MISMATCH"
    assert out.mismatch_vnd == abs(r.total - claimed)
    assert out.shares == {}
