"""Deterministic UI hints shared by Guardian_Web and the Eval_Harness (design.md, "UI hints")."""

from __future__ import annotations

from collections.abc import Collection, Sequence
from datetime import datetime, timedelta, timezone

from guardian.reason_codes import RC_COLD_START_NEEDS_CONTEXT
from guardian.schemas.api_models import ContextChoice, Prefill, TrustedContactRef, UiHints
from guardian.schemas.enums import Cue, DecisionTier

GMT7 = timezone(timedelta(hours=7))
LATE_NIGHT_START_HOUR = 23
LATE_NIGHT_END_HOUR = 5

_CALM_CUES: frozenset[Cue] = frozenset({Cue.URGENCY_TIME_PRESSURE, Cue.SECRECY_DO_NOT_TELL_ANYONE})
_REQUIRED_FIELDS: tuple[str, ...] = ("bank_bin", "account_number", "amount_vnd")


def is_late_night(client_time: datetime | None) -> bool:
    """True when ``client_time`` falls in [23:00, 05:00) GMT+7.

    A naive datetime is read as GMT+7 wall-clock time. ``None`` is never late night.
    """
    if client_time is None:
        return False
    local = client_time.replace(tzinfo=GMT7) if client_time.tzinfo is None else client_time.astimezone(GMT7)
    return local.hour >= LATE_NIGHT_START_HOUR or local.hour < LATE_NIGHT_END_HOUR


def missing_fields(prefill: Prefill | None) -> list[str]:
    """Return the required transfer fields absent from ``prefill`` (fixed order)."""
    missing: list[str] = []
    for name in _REQUIRED_FIELDS:
        value = getattr(prefill, name, None) if prefill is not None else None
        if value is None or value == "":
            missing.append(name)
    return missing


def compute_ui_hints(
    *,
    tier: DecisionTier,
    reason_codes: Collection[str],
    cues: Collection[Cue] = (),
    client_time: datetime | None = None,
    context: ContextChoice | None = None,
    prefill: Prefill | None = None,
    listing_requires_deposit: bool = False,
    trusted_contacts: Sequence[TrustedContactRef] = (),
    hotline: str | None = None,
) -> UiHints:
    cue_set = set(cues)
    calm_shield = (
        bool(cue_set & _CALM_CUES)
        or (tier != DecisionTier.ALLOW and is_late_night(client_time))
        or context == "AUTHORITY_REQUEST"
    )
    safe_payment_tips = (
        listing_requires_deposit
        or Cue.UPFRONT_DEPOSIT_OR_UNLOCK_FEE in cue_set
        or context == "ONLINE_ORDER"
    )
    missing = missing_fields(prefill)
    not_hard = tier != DecisionTier.HARD_HOLD
    return UiHints(
        calm_shield=calm_shield,
        show_context_elicitation=RC_COLD_START_NEEDS_CONTEXT in reason_codes,
        safe_payment_tips=safe_payment_tips,
        show_transfer_now=not_hard and prefill is not None and not missing,
        handoff_allowed=not_hard,
        missing_fields=missing,
        trusted_contacts=list(trusted_contacts) if calm_shield else [],
        hotline=hotline if calm_shield else None,
    )
