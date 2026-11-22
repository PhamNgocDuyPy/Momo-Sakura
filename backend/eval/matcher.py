"""Expectation matcher for scenario fixtures (mirrors ``web/src/lib/expectation.ts``).

``match(response, expect)`` returns a list of mismatch strings; empty means pass.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from datetime import datetime, timedelta
from typing import Any

from eval.scenario_loader import FIXTURES_DIR, get_path
from guardian.control_plane.tool_runner import ALLOWED_TOOLS

TIER_ORDER: dict[str, int] = {"ALLOW": 0, "SOFT_FRICTION": 1, "HARD_HOLD": 2}

# name -> fn(actual_value, args, response) -> bool
ReferenceFn = Callable[[Any, Mapping[str, Any], Mapping[str, Any]], bool]
REFERENCE_FUNCS: dict[str, ReferenceFn] = {}


def register_reference(name: str) -> Callable[[ReferenceFn], ReferenceFn]:
    def deco(fn: ReferenceFn) -> ReferenceFn:
        REFERENCE_FUNCS[name] = fn
        return fn

    return deco


@register_reference("equals_arg")
def _equals_arg(actual: Any, args: Mapping[str, Any], response: Mapping[str, Any]) -> bool:
    return actual == args.get("expected")


_SANDBOX_NOW = "2026-11-30T20:00:00+07:00"


def _reference_window(period: str, now: datetime) -> tuple[datetime, datetime, bool, bool]:
    """(lo, hi, lo_inclusive, hi_inclusive) written independently of ``features.spend_query``."""
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    monday = midnight - timedelta(days=midnight.weekday())
    first_this = midnight.replace(day=1)
    first_prev = (first_this - timedelta(days=1)).replace(day=1)
    first_prev2 = (first_prev - timedelta(days=1)).replace(day=1)
    table: dict[str, tuple[datetime, datetime, bool, bool]] = {
        "TODAY": (midnight, now, True, True),
        "YESTERDAY": (midnight - timedelta(days=1), midnight, True, False),
        "THIS_WEEK": (monday, now, True, True),
        "LAST_WEEK": (monday - timedelta(days=7), monday, True, False),
        "THIS_MONTH": (first_this, now, True, True),
        "LAST_MONTH": (first_prev, first_this, True, False),
        "LAST_7_DAYS": (now - timedelta(days=7), now, False, True),
        "LAST_30_DAYS": (now - timedelta(days=30), now, False, True),
        "LAST_3_MONTHS": (first_prev2, now, True, True),
    }
    return table[period]


@register_reference("spend_reference")
def _spend_reference(actual: Any, args: Mapping[str, Any], response: Mapping[str, Any]) -> bool:
    """Filter-and-aggregate over ``wallet_sandbox.json`` for TOTAL / COUNT / AVERAGE_PER_TXN / MAX_TXN.

    ``args``: ``category``, ``period``, ``metric`` and optional ``now`` (default SANDBOX_NOW).
    Reads the raw fixture, so it does not share code with ``Spend_Query_Engine``.
    """
    raw = json.loads((FIXTURES_DIR / "wallet_sandbox.json").read_text(encoding="utf-8"))
    now = datetime.fromisoformat(str(args.get("now", _SANDBOX_NOW)))
    category = str(args.get("category", "ALL"))
    metric = str(args.get("metric", "TOTAL"))
    try:
        lo, hi, lo_inc, hi_inc = _reference_window(str(args.get("period", "THIS_MONTH")), now)
    except KeyError:
        return False
    amounts: list[int] = []
    for tx in raw["transactions"]:
        at = datetime.fromisoformat(tx["at"]).astimezone(now.tzinfo)
        in_range = (at >= lo if lo_inc else at > lo) and (at <= hi if hi_inc else at < hi)
        if tx["direction"] == "OUT" and category in ("ALL", tx["category"]) and in_range:
            amounts.append(int(tx["amount_vnd"]))
    expected = {
        "TOTAL": sum(amounts),
        "COUNT": len(amounts),
        "AVERAGE_PER_TXN": sum(amounts) // len(amounts) if amounts else 0,
        "MAX_TXN": max(amounts, default=0),
    }.get(metric)
    return expected is not None and actual == expected


def _get(response: Mapping[str, Any], path: str) -> tuple[bool, Any]:
    try:
        return True, get_path(response, path)
    except KeyError:
        return False, None


def _tier(response: Mapping[str, Any]) -> str | None:
    verdict = response.get("verdict")
    if isinstance(verdict, Mapping) and "decision_tier" in verdict:
        return str(verdict["decision_tier"])
    value = response.get("decision_tier")
    return str(value) if value is not None else None


def _reason_codes(response: Mapping[str, Any]) -> list[str]:
    verdict = response.get("verdict")
    codes = verdict.get("reason_codes") if isinstance(verdict, Mapping) else response.get("reason_codes")
    return [str(c) for c in codes or []]


def _qr(response: Mapping[str, Any]) -> Mapping[str, Any]:
    qr = response.get("qr")
    return qr if isinstance(qr, Mapping) else {}


def _check_assert(response: Mapping[str, Any], spec: Mapping[str, Any]) -> str | None:
    path = str(spec.get("path", ""))
    op = spec.get("op")
    expected = spec.get("value")
    found, actual = _get(response, path)
    label = f"assert {path} {op}"
    if op == "absent":
        return None if not found or actual is None else f"{label}: found {actual!r}"
    if not found:
        return f"{label}: path not found"
    try:
        if op == "eq":
            ok = actual == expected
        elif op == "lt":
            ok = actual is not None and actual < expected
        elif op == "gt":
            ok = actual is not None and actual > expected
        elif op == "in":
            ok = actual in expected
        elif op == "contains":
            ok = expected in actual
        elif op == "matches_reference":
            if isinstance(expected, str):
                name, args = expected, {}
            else:
                name, args = str(expected.get("fn", "")), expected.get("args", {})
            fn = REFERENCE_FUNCS.get(name)
            if fn is None:
                return f"{label}: unknown reference function {name!r}"
            ok = fn(actual, args, response)
        else:
            return f"{label}: unsupported op"
    except TypeError:
        return f"{label}: incomparable value {actual!r} vs {expected!r}"
    return None if ok else f"{label}: expected {expected!r}, got {actual!r}"


def match(response: Mapping[str, Any], expect: Mapping[str, Any]) -> list[str]:
    """Compare an API response with a fixture ``expect`` block."""
    mismatches: list[str] = []

    if "decision_tier" in expect:
        want = expect["decision_tier"]
        got = _tier(response)
        if isinstance(want, Mapping):
            floor = str(want.get("min", ""))
            if floor not in TIER_ORDER:
                mismatches.append(f"decision_tier: invalid min {floor!r}")
            elif got not in TIER_ORDER or TIER_ORDER[got] < TIER_ORDER[floor]:
                mismatches.append(f"decision_tier: expected >= {floor}, got {got}")
        elif got != want:
            mismatches.append(f"decision_tier: expected {want}, got {got}")

    codes = set(_reason_codes(response))
    missing = [c for c in expect.get("reason_codes_include", []) if c not in codes]
    if missing:
        mismatches.append(f"reason_codes_include: missing {missing}")
    unexpected = [c for c in expect.get("reason_codes_exclude", []) if c in codes]
    if unexpected:
        mismatches.append(f"reason_codes_exclude: present {unexpected}")

    if "qr_result" in expect:
        got_qr = _qr(response).get("result")
        if got_qr != expect["qr_result"]:
            mismatches.append(f"qr_result: expected {expect['qr_result']}, got {got_qr}")
    if "qr_flags_include" in expect:
        flags = set(_qr(response).get("flags") or [])
        missing = [f for f in expect["qr_flags_include"] if f not in flags]
        if missing:
            mismatches.append(f"qr_flags_include: missing {missing}")
    if "stop_codes_include" in expect:
        stops = set(response.get("stop_codes") or [])
        missing = [s for s in expect["stop_codes_include"] if s not in stops]
        if missing:
            mismatches.append(f"stop_codes_include: missing {missing}")

    if expect.get("trace_tools_subset_of_allowlist"):
        bad = [
            str(step.get("name"))
            for step in response.get("trace") or []
            if step.get("kind") == "tool" and step.get("name") not in ALLOWED_TOOLS
        ]
        if bad:
            mismatches.append(f"trace_tools_subset_of_allowlist: not allowlisted {bad}")

    for spec in expect.get("assert", []):
        problem = _check_assert(response, spec)
        if problem:
            mismatches.append(problem)

    return mismatches
