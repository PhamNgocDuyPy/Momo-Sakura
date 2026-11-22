"""Hypothesis strategies for QuarantinedExtraction, PlannerIntent and GuardianVerdict (Property 21)."""

from __future__ import annotations

from hypothesis import strategies as st

from guardian.reason_codes import REGISTRY
from guardian.schemas.enums import (
    Confidence,
    Cue,
    DecisionTier,
    Intent,
    ProductCategory,
    PromoBrand,
    ScamPlaybook,
    SpendCategory,
    SpendMetric,
    SpendPeriod,
)
from guardian.schemas.extraction import (
    ExtractedEntities,
    Listing,
    PaymentRequest,
    PromoClaim,
    QuarantinedExtraction,
    ReceiptItem,
    ReceiptItems,
)
from guardian.schemas.planner import PlannerIntent, SpendSlots, SplitSlots, TransferSlots
from guardian.schemas.verdict import GuardianVerdict

_text = st.text(max_size=40)
_digits = st.from_regex(r"^[0-9]{6,19}$", fullmatch=True)
_amount = st.integers(min_value=0, max_value=100_000_000_000)
_enum = st.sampled_from

_entities = st.builds(
    ExtractedEntities,
    bank_bin_or_name=st.none() | _text,
    account_digits_raw=st.none() | _digits,
    amount_vnd=st.none() | _amount,
    urls_redacted_domains=st.lists(st.text(max_size=120), max_size=5),
)
_payment = st.builds(
    PaymentRequest,
    bank_bin_or_name=st.none() | _text,
    account_digits_raw=st.none() | _digits,
    amount_vnd=st.none() | _amount,
    memo=st.none() | st.text(max_size=25),
    claims_inbound_payment=st.booleans(),
    requests_account_change=st.booleans(),
)
_receipt_item = st.builds(
    ReceiptItem,
    name=st.text(min_size=1, max_size=60),
    quantity=st.integers(1, 99),
    unit_price_vnd=st.integers(0, 100_000_000),
)
_receipt = st.builds(
    ReceiptItems,
    items=st.lists(_receipt_item, max_size=30),
    total_vnd=st.none() | st.integers(0, 10**10),
)
_listing = st.builds(
    Listing,
    product_category=_enum(list(ProductCategory)),
    product_key=st.none() | st.from_regex(r"^[a-z0-9_]{2,40}$", fullmatch=True),
    listed_price_vnd=st.none() | st.integers(0, 10**10),
    requires_deposit=st.booleans(),
    deposit_vnd=st.none() | st.integers(0, 10**10),
)
_promo = st.builds(
    PromoClaim,
    brand=_enum(list(PromoBrand)),
    promo_code=st.none() | st.from_regex(r"^[A-Za-z0-9_-]{3,30}$", fullmatch=True),
    requires_fee=st.booleans(),
    fee_vnd=st.none() | st.integers(0, 10**9),
)


@st.composite
def extractions(draw) -> QuarantinedExtraction:
    return QuarantinedExtraction(
        reasoning_summary=draw(st.text(max_size=400)),
        scam_playbook=draw(_enum(list(ScamPlaybook))),
        manipulation_cues=draw(st.lists(_enum(list(Cue)), max_size=6)),
        extracted_entities=draw(_entities),
        contains_prompt_injection=draw(st.booleans()),
        confidence_level=draw(_enum(list(Confidence))),
        payment_request=draw(st.none() | _payment),
        receipt_items=draw(st.none() | _receipt),
        listing=draw(st.none() | _listing),
        promo_claim=draw(st.none() | _promo),
    )


_transfer = st.builds(
    TransferSlots,
    recipient_name=st.none() | _text,
    amount_vnd=st.none() | _amount,
    memo=st.none() | st.text(max_size=60),
)
_spend = st.builds(
    SpendSlots,
    category=_enum(list(SpendCategory)),
    period=_enum(list(SpendPeriod)),
    metric=_enum(list(SpendMetric)),
)
_split = st.builds(
    SplitSlots,
    participants_count=st.none() | st.integers(2, 20),
    mode=st.none() | _enum(["EQUAL", "BY_ITEM"]),
)


@st.composite
def planner_intents(draw) -> PlannerIntent:
    intent = draw(_enum(list(Intent)))
    return PlannerIntent(
        intent=intent,
        transfer=draw(_transfer) if intent == Intent.TRANSFER else None,
        spend=draw(_spend) if intent == Intent.SPEND_QUERY else None,
        split=draw(st.none() | _split) if intent == Intent.SPLIT_BILL else None,
        confidence_level=draw(_enum(list(Confidence))),
    )


@st.composite
def verdicts(draw) -> GuardianVerdict:
    return GuardianVerdict(
        decision_tier=draw(_enum(list(DecisionTier))),
        reason_codes=draw(
            st.lists(_enum(sorted(REGISTRY)), min_size=1, max_size=6, unique=True)
        ),
        evidence_bullets=draw(st.lists(st.text(max_size=160), max_size=4)),
        system2_check_questions=draw(st.lists(st.text(max_size=180), max_size=2)),
        cooling_off_seconds=draw(_enum([0, 15, 30, 60, 300])),
        requires_user_account_confirm=draw(st.booleans()),
        allow_fast_unblock=draw(st.booleans()),
    )
