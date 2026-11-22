"""Promo_Checker (F5): compare a promo claim with the official sandbox promo list.

Pure function. The official list is injected (loaded by ``providers/``); the returned
``official_promo`` always comes from that list, never from LLM output.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

from guardian.policy.floors import DecisionTier, Floor, HardSource
from guardian.reason_codes import (
    RC_BRAND_IMPERSONATION_MOMO,
    RC_FAKE_PROMO_REFUND,
    RC_PROMO_MATCHES_OFFICIAL_LIST,
    RC_PROMO_NOT_IN_OFFICIAL_LIST,
)
from guardian.schemas.enums import Cue, PromoBrand
from guardian.schemas.extraction import PromoClaim

_GMT7 = timezone(timedelta(hours=7))


@dataclass(frozen=True)
class OfficialPromo:
    brand: str
    promo_code: str
    title_vi: str
    valid_from: date
    valid_to: date
    min_order_vnd: int = 0


@dataclass(frozen=True)
class PromoCheckResult:
    floors: tuple[Floor, ...]
    reason_codes: tuple[str, ...]
    tier: DecisionTier
    matched: bool
    official_promo: OfficialPromo | None = None


def parse_official_promos(rows: Iterable[dict[str, object]]) -> list[OfficialPromo]:
    return [
        OfficialPromo(
            brand=str(r["brand"]),
            promo_code=str(r["promo_code"]),
            title_vi=str(r.get("title_vi", "")),
            valid_from=date.fromisoformat(str(r["valid_from"])),
            valid_to=date.fromisoformat(str(r["valid_to"])),
            min_order_vnd=int(r.get("min_order_vnd", 0)),  # type: ignore[call-overload]
        )
        for r in rows
    ]


def sandbox_today(now: datetime) -> date:
    """Calendar date in GMT+7 for the given instant."""
    return now.astimezone(_GMT7).date()


def match_official(
    claim: PromoClaim, promos: Sequence[OfficialPromo], today: date
) -> OfficialPromo | None:
    if claim.promo_code is None:
        return None
    code = claim.promo_code.casefold()
    for p in promos:
        if (
            p.brand == claim.brand.value
            and p.promo_code.casefold() == code
            and p.valid_from <= today <= p.valid_to
        ):
            return p
    return None


def _hard(code: str) -> Floor:
    return Floor(DecisionTier.HARD_HOLD, code, "F5", hard_source=HardSource.PROMO_FAKE)


def check_promo(
    claim: PromoClaim,
    promos: Sequence[OfficialPromo],
    now: datetime,
    cues: Iterable[Cue] = (),
) -> PromoCheckResult:
    """First true row wins: match, MOMO impersonation, fee/upfront, then unlisted."""
    official = match_official(claim, promos, sandbox_today(now))
    if official is not None:
        return PromoCheckResult(
            floors=(Floor(DecisionTier.ALLOW, RC_PROMO_MATCHES_OFFICIAL_LIST, "F5"),),
            reason_codes=(RC_PROMO_MATCHES_OFFICIAL_LIST,),
            tier=DecisionTier.ALLOW,
            matched=True,
            official_promo=official,
        )

    has_fee = claim.requires_fee or Cue.UPFRONT_DEPOSIT_OR_UNLOCK_FEE in set(cues)
    if claim.brand == PromoBrand.MOMO:
        codes = [RC_BRAND_IMPERSONATION_MOMO]
        if has_fee:
            codes.append(RC_FAKE_PROMO_REFUND)
        return PromoCheckResult(
            floors=tuple(_hard(c) for c in codes),
            reason_codes=tuple(codes),
            tier=DecisionTier.HARD_HOLD,
            matched=False,
        )
    if has_fee:
        return PromoCheckResult(
            floors=(_hard(RC_FAKE_PROMO_REFUND),),
            reason_codes=(RC_FAKE_PROMO_REFUND,),
            tier=DecisionTier.HARD_HOLD,
            matched=False,
        )
    return PromoCheckResult(
        floors=(Floor(DecisionTier.SOFT_FRICTION, RC_PROMO_NOT_IN_OFFICIAL_LIST, "F5"),),
        reason_codes=(RC_PROMO_NOT_IN_OFFICIAL_LIST,),
        tier=DecisionTier.SOFT_FRICTION,
        matched=False,
    )
