"""Hypothesis strategies for wallet transactions and budgets."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from hypothesis import strategies as st

from guardian.providers.base import Budget, WalletTransaction
from guardian.schemas.enums import SpendCategory

TZ = timezone(timedelta(hours=7))
NOW = datetime(2026, 11, 30, 20, 0, tzinfo=TZ)

_CATEGORIES = [c for c in SpendCategory if c is not SpendCategory.ALL]


@st.composite
def wallet_transactions(draw: st.DrawFn, max_size: int = 40) -> list[WalletTransaction]:
    n = draw(st.integers(0, max_size))
    txs: list[WalletTransaction] = []
    for i in range(n):
        # Span roughly two months so both in-month and out-of-month rows appear.
        minutes_ago = draw(st.integers(0, 60 * 24 * 60))
        txs.append(
            WalletTransaction(
                id=f"tx_{i:04d}",
                at=NOW - timedelta(minutes=minutes_ago),
                direction=draw(st.sampled_from(["IN", "OUT"])),
                category=draw(st.sampled_from(_CATEGORIES)),
                counterparty=draw(st.sampled_from(["A", "B", "C"])),
                amount_vnd=draw(st.integers(1_000, 5_000_000)),
            )
        )
    return txs


@st.composite
def budgets(draw: st.DrawFn) -> list[Budget]:
    cats = draw(st.lists(st.sampled_from(_CATEGORIES), unique=True, max_size=4))
    return [Budget(category=c, limit_vnd=draw(st.integers(1, 20_000_000))) for c in cats]
