# Feature: momo-guardian-web, Property 36/37: Shop_Checker price flag and Promo_Checker decision table
"""Properties 36 and 37 plus small unit examples (A08, A09, A10, T04, T12).

**Validates: Requirements 23.2, 23.5, 24.2, 24.3, 24.4, 24.5**
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from hypothesis import given
from hypothesis import strategies as st

from guardian.features.promo_checker import (
    OfficialPromo,
    check_promo,
    match_official,
    parse_official_promos,
    sandbox_today,
)
from guardian.features.shop_checker import ReferencePrice, check_listing, parse_reference_prices
from guardian.policy.floors import DecisionTier, HardSource
from guardian.providers.fixture_loader import load_json, resolve_fixtures_dir
from guardian.reason_codes import (
    RC_BRAND_IMPERSONATION_MOMO,
    RC_FAKE_PROMO_REFUND,
    RC_NO_REFERENCE_PRICE,
    RC_PRICE_TOO_GOOD_TO_BE_TRUE,
    RC_PROMO_MATCHES_OFFICIAL_LIST,
    RC_PROMO_NOT_IN_OFFICIAL_LIST,
)
from guardian.schemas.enums import Cue, ProductCategory, PromoBrand
from guardian.schemas.extraction import Listing, PromoClaim
from tests.property.strategies.promo import official_promo_lists, promo_claims, promo_cues

NOW = datetime(2026, 11, 30, 20, 0, tzinfo=timezone(timedelta(hours=7)))


def _fixture(name: str):  # tests may read fixtures through the provider loader
    return load_json(resolve_fixtures_dir("<default>"), name)


@given(
    listed=st.integers(0, 200_000_000),
    ref=st.integers(1, 200_000_000),
    with_ref=st.booleans(),
)
def test_p36_price_flag(listed: int, ref: int, with_ref: bool) -> None:
    prices = [ReferencePrice("item_x", "PHONE", ref)] if with_ref else []
    res = check_listing(Listing(product_key="item_x", listed_price_vnd=listed), prices)
    if with_ref:
        flagged = listed * 100 <= ref * 60
        assert (RC_PRICE_TOO_GOOD_TO_BE_TRUE in res.reason_codes) == flagged
        assert (res.tier >= DecisionTier.SOFT_FRICTION) == flagged
        assert RC_NO_REFERENCE_PRICE not in res.reason_codes
    else:
        assert RC_NO_REFERENCE_PRICE in res.reason_codes
        assert RC_PRICE_TOO_GOOD_TO_BE_TRUE not in res.reason_codes


@given(data=st.data(), cues=promo_cues)
def test_p37_promo_decision_table(data: st.DataObject, cues: list[Cue]) -> None:
    promos = data.draw(official_promo_lists())
    claim = data.draw(promo_claims(promos))
    res = check_promo(claim, promos, NOW, cues)
    today = sandbox_today(NOW)
    matched = any(
        p.brand == claim.brand.value
        and claim.promo_code is not None
        and p.promo_code.casefold() == claim.promo_code.casefold()
        and p.valid_from <= today <= p.valid_to
        for p in promos
    )
    fee = claim.requires_fee or Cue.UPFRONT_DEPOSIT_OR_UNLOCK_FEE in cues
    if matched:
        assert res.reason_codes == (RC_PROMO_MATCHES_OFFICIAL_LIST,)
        assert res.tier == DecisionTier.ALLOW and res.official_promo is not None
    elif claim.brand == PromoBrand.MOMO:
        assert res.reason_codes[0] == RC_BRAND_IMPERSONATION_MOMO
        assert res.tier == DecisionTier.HARD_HOLD
    elif fee:
        assert res.reason_codes == (RC_FAKE_PROMO_REFUND,)
        assert res.tier == DecisionTier.HARD_HOLD
    else:
        assert res.reason_codes == (RC_PROMO_NOT_IN_OFFICIAL_LIST,)
        assert res.tier == DecisionTier.SOFT_FRICTION
    for f in res.floors:
        if f.tier == DecisionTier.HARD_HOLD:
            assert f.hard_source == HardSource.PROMO_FAKE


def test_a10_iphone_cheap_with_deposit() -> None:
    prices = parse_reference_prices(_fixture("reference_prices.json"))
    listing = Listing(
        product_category=ProductCategory.PHONE,
        product_key="iphone_15_pro_max",
        listed_price_vnd=9_000_000,
        requires_deposit=True,
        deposit_vnd=2_000_000,
    )
    res = check_listing(listing, prices)
    assert res.reason_codes == (RC_PRICE_TOO_GOOD_TO_BE_TRUE,)
    assert res.discount_percent == 64
    assert res.safe_payment_tips is True


def test_category_fallback_and_missing_reference() -> None:
    prices = [ReferencePrice(None, "SNEAKERS", 2_000_000)]
    hit = check_listing(Listing(product_category=ProductCategory.SNEAKERS, listed_price_vnd=500_000), prices)
    assert RC_PRICE_TOO_GOOD_TO_BE_TRUE in hit.reason_codes
    miss = check_listing(Listing(product_category=ProductCategory.CAMERA, listed_price_vnd=1), prices)
    assert miss.reason_codes == (RC_NO_REFERENCE_PRICE,)


def test_promo_fixture_examples() -> None:
    promos = parse_official_promos(_fixture("official_promos.json"))
    a08 = check_promo(PromoClaim(brand=PromoBrand.MOMO, promo_code="momoxmas26"), promos, NOW)
    assert a08.matched and a08.official_promo is not None and a08.official_promo.promo_code == "MOMOXMAS26"
    a09 = check_promo(PromoClaim(brand=PromoBrand.MOMO, requires_fee=True), promos, NOW)
    assert set(a09.reason_codes) == {RC_BRAND_IMPERSONATION_MOMO, RC_FAKE_PROMO_REFUND}
    # Before valid_from the code is not yet official.
    early = datetime(2026, 11, 14, 12, 0, tzinfo=timezone(timedelta(hours=7)))
    assert match_official(PromoClaim(brand=PromoBrand.MOMO, promo_code="MOMOXMAS26"), promos, sandbox_today(early)) is None
    t12 = check_promo(PromoClaim(brand=PromoBrand.SHOPEE, promo_code="ABC123"), promos, NOW, [Cue.UPFRONT_DEPOSIT_OR_UNLOCK_FEE])
    assert t12.reason_codes == (RC_FAKE_PROMO_REFUND,)
    assert isinstance(promos[0], OfficialPromo)
