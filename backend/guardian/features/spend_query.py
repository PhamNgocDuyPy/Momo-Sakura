"""Spend_Query_Engine (F6): pure ``compute(txns, slots, now)`` over OUT transactions.

Periods are calendar windows in the timezone of ``now`` (SandboxClock). A window is
``(lo, hi)`` with inclusive flags: windows that end at ``now`` include ``now``; the rolling
7/30-day windows exclude their start. ``COMPARE_PREVIOUS`` compares with the window of the same
length that ends where the current one starts. The series holds per-bucket spend totals
(VND) for buckets that have at least one transaction: days, or weeks (Monday start) for
``LAST_3_MONTHS``.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from guardian.policy import templates_vi as tv
from guardian.providers.base import WalletTransaction
from guardian.schemas.api_models import SpendQueryResponse, SpendRange, SpendSeriesPoint
from guardian.schemas.enums import SpendCategory, SpendMetric, SpendPeriod
from guardian.schemas.planner import SpendSlots
from guardian.tools.amount import format_vnd

SpendResult = SpendQueryResponse


@dataclass(frozen=True)
class _Window:
    lo: datetime
    hi: datetime
    lo_inclusive: bool = True
    hi_inclusive: bool = False

    def contains(self, at: datetime) -> bool:
        above = at >= self.lo if self.lo_inclusive else at > self.lo
        below = at <= self.hi if self.hi_inclusive else at < self.hi
        return above and below

    def previous(self) -> _Window:
        length = self.hi - self.lo
        return _Window(self.lo - length, self.lo, self.lo_inclusive, not self.lo_inclusive)

    def last_date(self) -> date:
        return (self.hi if self.hi_inclusive else self.hi - timedelta(microseconds=1)).date()


def _midnight(day: datetime) -> datetime:
    return day.replace(hour=0, minute=0, second=0, microsecond=0)


def _month_start(now: datetime, months_back: int) -> datetime:
    index = now.year * 12 + (now.month - 1) - months_back
    return _midnight(now).replace(year=index // 12, month=index % 12 + 1, day=1)


def window_for(period: SpendPeriod, now: datetime) -> _Window:
    today = _midnight(now)
    monday = today - timedelta(days=today.weekday())
    if period == SpendPeriod.TODAY:
        return _Window(today, now, hi_inclusive=True)
    if period == SpendPeriod.YESTERDAY:
        return _Window(today - timedelta(days=1), today)
    if period == SpendPeriod.THIS_WEEK:
        return _Window(monday, now, hi_inclusive=True)
    if period == SpendPeriod.LAST_WEEK:
        return _Window(monday - timedelta(days=7), monday)
    if period == SpendPeriod.THIS_MONTH:
        return _Window(_month_start(now, 0), now, hi_inclusive=True)
    if period == SpendPeriod.LAST_MONTH:
        return _Window(_month_start(now, 1), _month_start(now, 0))
    if period == SpendPeriod.LAST_7_DAYS:
        return _Window(now - timedelta(days=7), now, lo_inclusive=False, hi_inclusive=True)
    if period == SpendPeriod.LAST_30_DAYS:
        return _Window(now - timedelta(days=30), now, lo_inclusive=False, hi_inclusive=True)
    return _Window(_month_start(now, 2), now, hi_inclusive=True)  # LAST_3_MONTHS


def _select(
    txns: Iterable[WalletTransaction], category: SpendCategory, window: _Window, tz: object
) -> list[WalletTransaction]:
    return [
        t
        for t in txns
        if t.direction == "OUT"
        and (category == SpendCategory.ALL or t.category == category)
        and window.contains(t.at.astimezone(tz))  # type: ignore[arg-type]
    ]


def _metric_value(metric: SpendMetric, selected: list[WalletTransaction], days: int) -> int:
    amounts = [t.amount_vnd for t in selected]
    total = sum(amounts)
    if metric == SpendMetric.COUNT:
        return len(amounts)
    if metric == SpendMetric.AVERAGE_PER_TXN:
        return total // len(amounts) if amounts else 0
    if metric == SpendMetric.AVERAGE_PER_DAY:
        return total // days
    if metric == SpendMetric.MAX_TXN:
        return max(amounts, default=0)
    return total  # TOTAL and COMPARE_PREVIOUS (current period total)


def _series(
    selected: list[WalletTransaction], weekly: bool, tz: object
) -> list[SpendSeriesPoint]:
    buckets: dict[str, int] = defaultdict(int)
    for t in selected:
        day = t.at.astimezone(tz).date()  # type: ignore[arg-type]
        if weekly:
            day = day - timedelta(days=day.weekday())
        buckets[day.isoformat()] += t.amount_vnd
    return [SpendSeriesPoint(bucket=b, value=v) for b, v in sorted(buckets.items())]


def _cap(text: str) -> str:
    return text[:1].upper() + text[1:]


def _delta_text(delta: int | None, current: int, previous: int) -> str:
    if delta is None:
        return tv.F6_DELTA_UNKNOWN
    if current == previous:
        return tv.F6_DELTA_SAME
    template = tv.F6_DELTA_UP if delta > 0 else tv.F6_DELTA_DOWN
    return template.format(percent=abs(delta))


def compute(txns: Iterable[WalletTransaction], slots: SpendSlots, now: datetime) -> SpendResult:
    tz = now.tzinfo
    txns = list(txns)
    window = window_for(slots.period, now)
    selected = _select(txns, slots.category, window, tz)
    days = (window.last_date() - window.lo.date()).days + 1
    value = _metric_value(slots.metric, selected, days)
    is_count = slots.metric == SpendMetric.COUNT

    previous_value: int | None = None
    delta: int | None = None
    prev_selected: list[WalletTransaction] = []
    if slots.metric == SpendMetric.COMPARE_PREVIOUS:
        prev_selected = _select(txns, slots.category, window.previous(), tz)
        previous_value = sum(t.amount_vnd for t in prev_selected)
        if previous_value:
            delta = round((value - previous_value) * 100 / previous_value)

    period_text = _cap(slots.period.label_vi)
    category_text = (
        tv.F6_ALL_CATEGORIES if slots.category == SpendCategory.ALL else slots.category.label_vi
    )
    no_data = not selected and slots.metric not in (SpendMetric.COUNT, SpendMetric.COMPARE_PREVIOUS)
    if slots.metric == SpendMetric.COMPARE_PREVIOUS and not selected and not prev_selected:
        no_data = True
    if no_data:
        answer = tv.F6_NO_DATA.format(period=period_text, category=category_text)
    else:
        answer = tv.F6_ANSWERS[slots.metric].format(
            period=period_text,
            category=category_text,
            value=str(value) if is_count else format_vnd(value),
            count=len(selected),
            previous=format_vnd(previous_value or 0),
            delta=_delta_text(delta, value, previous_value or 0),
        )

    return SpendResult(
        value=value,
        unit="COUNT" if is_count else "VND",
        previous_value=previous_value,
        delta_percent=delta,
        range=SpendRange(from_=window.lo, to=window.hi),
        series=_series(selected, slots.period == SpendPeriod.LAST_3_MONTHS, tz),
        bucket_unit="WEEK" if slots.period == SpendPeriod.LAST_3_MONTHS else "DAY",
        answer_vi=answer,
    )
