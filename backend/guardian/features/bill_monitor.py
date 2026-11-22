"""Bill_Monitor (F7): pure, integer-only alerts over bills and subscriptions."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta

from guardian.providers.base import BillRecord, Subscription
from guardian.schemas.api_models import (
    BillSpikeAlert,
    RenewalSoonAlert,
    UnusedSubscriptionAlert,
)

SPIKE_PERCENT = 30
RENEWAL_WINDOW_DAYS = 7
UNUSED_DAYS = 30

Alert = BillSpikeAlert | RenewalSoonAlert | UnusedSubscriptionAlert


def _round_div(num: int, den: int) -> int:
    """Round-half-up integer division for non-negative num and positive den."""
    return (2 * num + den) // (2 * den)


def spike_alerts(bills: list[BillRecord]) -> list[BillSpikeAlert]:
    by_provider: dict[str, list[BillRecord]] = defaultdict(list)
    for b in bills:
        by_provider[b.provider_id].append(b)
    out: list[BillSpikeAlert] = []
    for provider_id in sorted(by_provider):
        history = sorted(by_provider[provider_id], key=lambda b: b.period)
        if len(history) < 4:  # current + 3 previous periods
            continue
        current = history[-1].amount_vnd
        sum3 = sum(b.amount_vnd for b in history[-4:-1])
        if current * 3 * 100 >= (100 + SPIKE_PERCENT) * sum3:
            # sum3 == 0 means any positive bill is a spike; avoid dividing by zero.
            pct = _round_div((current * 3 - sum3) * 100, sum3) if sum3 > 0 else 0
            out.append(
                BillSpikeAlert(
                    provider_id=provider_id,
                    current_vnd=current,
                    avg3_vnd=sum3 // 3,
                    increase_percent=pct,
                )
            )
    return out


def alerts(bills: list[BillRecord], subs: list[Subscription], now: datetime) -> list[Alert]:
    """BILL_SPIKE, then RENEWAL_SOON, then UNUSED_SUBSCRIPTION (each in stable order)."""
    today = now.date()
    result: list[Alert] = list(spike_alerts(bills))
    for s in sorted(subs, key=lambda s: s.id):
        days_left = (s.renewal_date - today).days
        if 0 <= days_left <= RENEWAL_WINDOW_DAYS:
            result.append(
                RenewalSoonAlert(
                    subscription_id=s.id,
                    renewal_date=s.renewal_date.isoformat(),
                    amount_vnd=s.amount_vnd,
                    days_left=days_left,
                )
            )
    for s in sorted(subs, key=lambda s: s.id):
        if s.last_used_at is None:
            # Never used: the exact age is unknown; report the threshold as a lower bound.
            result.append(
                UnusedSubscriptionAlert(subscription_id=s.id, days_since_last_use=UNUSED_DAYS)
            )
        elif now - s.last_used_at >= timedelta(days=UNUSED_DAYS):
            last_local = s.last_used_at.astimezone(now.tzinfo).date()
            result.append(
                UnusedSubscriptionAlert(
                    subscription_id=s.id, days_since_last_use=(today - last_local).days
                )
            )
    return result
