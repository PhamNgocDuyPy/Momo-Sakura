"""Wallet summary for the dashboard (GET /api/wallet/summary). Pure over provider data."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from guardian.features.bill_monitor import alerts as bill_alerts
from guardian.providers.base import (
    Budget,
    TrustedContact,
    WalletDataProvider,
    WalletTransaction,
)
from guardian.schemas.enums import SpendCategory


class _Out(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CategorySpend(_Out):
    category: SpendCategory
    label_vi: str
    total_vnd: int


class BudgetStatus(_Out):
    category: SpendCategory
    label_vi: str
    limit_vnd: int
    spent_vnd: int
    percent_used: int
    status: Literal["OK", "WARNING", "OVER"]


class ShieldStatsOut(_Out):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    checks: int = 0
    ALLOW: int = 0
    SOFT_FRICTION: int = 0
    HARD_HOLD: int = 0


class WalletSummary(_Out):
    as_of: datetime
    month: str
    sandbox: bool = True
    spending_by_category: list[CategorySpend]
    budgets: list[BudgetStatus]
    recent_transactions: list[dict[str, Any]]
    bills: list[dict[str, Any]]
    subscriptions: list[dict[str, Any]]
    alerts: list[dict[str, Any]]
    trusted_contacts: list[TrustedContact]
    shield_stats: ShieldStatsOut


def budget_status(spent: int, limit: int) -> tuple[int, Literal["OK", "WARNING", "OVER"]]:
    """Integer-only percent and status (no float rounding)."""
    percent = (spent * 100) // limit
    if spent >= limit:
        return percent, "OVER"
    if spent * 100 >= limit * 80:
        return percent, "WARNING"
    return percent, "OK"


def _in_month(tx: WalletTransaction, now: datetime) -> bool:
    local = tx.at.astimezone(now.tzinfo)
    return local.year == now.year and local.month == now.month


def spending_by_category(txs: list[WalletTransaction], now: datetime) -> dict[SpendCategory, int]:
    totals: dict[SpendCategory, int] = defaultdict(int)
    for tx in txs:
        if tx.direction == "OUT" and _in_month(tx, now):
            totals[tx.category] += tx.amount_vnd
    return dict(totals)


def build_budgets(budgets: list[Budget], spent: dict[SpendCategory, int]) -> list[BudgetStatus]:
    out: list[BudgetStatus] = []
    for b in budgets:
        s = spent.get(b.category, 0)
        percent, status = budget_status(s, b.limit_vnd)
        out.append(
            BudgetStatus(
                category=b.category,
                label_vi=b.category.label_vi,
                limit_vnd=b.limit_vnd,
                spent_vnd=s,
                percent_used=percent,
                status=status,
            )
        )
    return out


def build_wallet_summary(
    wallet: WalletDataProvider,
    now: datetime,
    shield_stats: dict[str, int],
) -> WalletSummary:
    txs = wallet.transactions()
    spent = spending_by_category(txs, now)
    recent = sorted(txs, key=lambda t: t.at, reverse=True)[:10]
    return WalletSummary(
        as_of=now,
        month=f"{now.year:04d}-{now.month:02d}",
        spending_by_category=[
            CategorySpend(category=c, label_vi=c.label_vi, total_vnd=total)
            for c, total in sorted(spent.items(), key=lambda kv: (-kv[1], kv[0].value))
        ],
        budgets=build_budgets(wallet.budgets(), spent),
        recent_transactions=[t.model_dump(mode="json") for t in recent],
        bills=[b.model_dump(mode="json") for b in wallet.bills()],
        subscriptions=[s.model_dump(mode="json") for s in wallet.subscriptions()],
        alerts=[a.model_dump(mode="json") for a in bill_alerts(wallet.bills(), wallet.subscriptions(), now)],
        trusted_contacts=wallet.trusted_contacts(),
        shield_stats=ShieldStatsOut(**shield_stats),
    )
