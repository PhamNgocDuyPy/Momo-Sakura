"""Shop_Checker (F4): compare a listed price with a sandbox reference price.

Pure function. Reference prices are injected (loaded by ``providers/``), never read from disk here.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field

from guardian.policy.floors import DecisionTier, Floor
from guardian.reason_codes import RC_NO_REFERENCE_PRICE, RC_PRICE_TOO_GOOD_TO_BE_TRUE
from guardian.schemas.enums import Cue
from guardian.schemas.extraction import Listing
from guardian.tools.url_checker import UrlCheckResult


@dataclass(frozen=True)
class ReferencePrice:
    product_key: str | None
    category: str
    reference_price_vnd: int
    source_note: str = ""


@dataclass(frozen=True)
class ShopCheckResult:
    floors: tuple[Floor, ...]
    reason_codes: tuple[str, ...]
    tier: DecisionTier
    reference_price_vnd: int | None
    listed_price_vnd: int | None
    discount_percent: int | None
    url_results: tuple[UrlCheckResult, ...] = field(default_factory=tuple)
    safe_payment_tips: bool = False


def parse_reference_prices(rows: Iterable[dict[str, object]]) -> list[ReferencePrice]:
    return [
        ReferencePrice(
            product_key=r.get("product_key") or None,  # type: ignore[arg-type]
            category=str(r.get("category", "")),
            reference_price_vnd=int(r["reference_price_vnd"]),  # type: ignore[call-overload]
            source_note=str(r.get("source_note", "")),
        )
        for r in rows
    ]


def find_reference(listing: Listing, prices: Sequence[ReferencePrice]) -> ReferencePrice | None:
    """Look up by ``product_key`` first, then by category entries that have no product key."""
    if listing.product_key is not None:
        for p in prices:
            if p.product_key == listing.product_key:
                return p
    for p in prices:
        if p.product_key is None and p.category == listing.product_category.value:
            return p
    return None


def is_too_good(listed_vnd: int, reference_vnd: int) -> bool:
    """Integer check: at least 40% below reference."""
    return listed_vnd * 100 <= reference_vnd * 60


def check_listing(
    listing: Listing,
    prices: Sequence[ReferencePrice],
    urls: Sequence[UrlCheckResult] = (),
    cues: Iterable[Cue] = (),
) -> ShopCheckResult:
    ref = find_reference(listing, prices)
    floors: list[Floor] = []
    codes: list[str] = []
    discount: int | None = None
    listed = listing.listed_price_vnd

    if ref is None:
        codes.append(RC_NO_REFERENCE_PRICE)
        floors.append(Floor(DecisionTier.ALLOW, RC_NO_REFERENCE_PRICE, "F4"))
    elif listed is not None and ref.reference_price_vnd > 0:
        if is_too_good(listed, ref.reference_price_vnd):
            codes.append(RC_PRICE_TOO_GOOD_TO_BE_TRUE)
            floors.append(Floor(DecisionTier.SOFT_FRICTION, RC_PRICE_TOO_GOOD_TO_BE_TRUE, "F4"))
        discount = max(0, (ref.reference_price_vnd - listed) * 100 // ref.reference_price_vnd)

    deposit = (
        listing.requires_deposit
        or bool(listing.deposit_vnd)
        or Cue.UPFRONT_DEPOSIT_OR_UNLOCK_FEE in set(cues)
    )
    tier = max((f.tier for f in floors), default=DecisionTier.ALLOW)
    return ShopCheckResult(
        floors=tuple(floors),
        reason_codes=tuple(codes),
        tier=tier,
        reference_price_vnd=ref.reference_price_vnd if ref else None,
        listed_price_vnd=listed,
        discount_percent=discount,
        url_results=tuple(urls),
        safe_payment_tips=deposit,
    )
