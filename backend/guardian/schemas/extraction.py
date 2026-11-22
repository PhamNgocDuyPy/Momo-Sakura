"""QuarantinedExtraction: the only shape the Quarantined_Extractor may emit (design.md)."""

from __future__ import annotations

from typing import Annotated

from pydantic import Field

from guardian.schemas.base import Strict
from guardian.schemas.enums import (
    Confidence,
    Cue,
    ProductCategory,
    PromoBrand,
    ScamPlaybook,
)

Short40 = Annotated[str, Field(max_length=40)]
Domain = Annotated[str, Field(max_length=120)]
AccountDigits = Annotated[str, Field(pattern=r"^[0-9]{6,19}$")]
ExtractedAmount = Annotated[int, Field(ge=0, le=100_000_000_000)]


class ExtractedEntities(Strict):
    bank_bin_or_name: Short40 | None = None
    account_digits_raw: AccountDigits | None = None
    amount_vnd: ExtractedAmount | None = None
    urls_redacted_domains: Annotated[list[Domain], Field(max_length=5)] = []


class PaymentRequest(Strict):
    bank_bin_or_name: Short40 | None = None
    account_digits_raw: AccountDigits | None = None
    amount_vnd: ExtractedAmount | None = None
    memo: Annotated[str, Field(max_length=25)] | None = None
    claims_inbound_payment: bool = False
    requests_account_change: bool = False


class ReceiptItem(Strict):
    name: Annotated[str, Field(min_length=1, max_length=60)]
    quantity: Annotated[int, Field(ge=1, le=99)]
    unit_price_vnd: Annotated[int, Field(ge=0, le=100_000_000)]


class ReceiptItems(Strict):
    items: Annotated[list[ReceiptItem], Field(max_length=30)] = []
    total_vnd: Annotated[int, Field(ge=0)] | None = None


class Listing(Strict):
    product_category: ProductCategory = ProductCategory.OTHER
    product_key: Annotated[str, Field(pattern=r"^[a-z0-9_]{2,40}$")] | None = None
    listed_price_vnd: Annotated[int, Field(ge=0)] | None = None
    requires_deposit: bool = False
    deposit_vnd: Annotated[int, Field(ge=0)] | None = None


class PromoClaim(Strict):
    brand: PromoBrand = PromoBrand.OTHER
    promo_code: Annotated[str, Field(pattern=r"^[A-Za-z0-9_-]{3,30}$")] | None = None
    requires_fee: bool = False
    fee_vnd: Annotated[int, Field(ge=0)] | None = None


class QuarantinedExtraction(Strict):
    reasoning_summary: Annotated[str, Field(max_length=400)]  # first field (Req 13.3)
    scam_playbook: ScamPlaybook
    manipulation_cues: Annotated[list[Cue], Field(max_length=6)] = []
    extracted_entities: ExtractedEntities = ExtractedEntities()
    contains_prompt_injection: bool
    confidence_level: Confidence
    payment_request: PaymentRequest | None = None
    receipt_items: ReceiptItems | None = None
    listing: Listing | None = None
    promo_claim: PromoClaim | None = None


FALLBACK_EXTRACTION = QuarantinedExtraction(
    reasoning_summary="fallback",
    scam_playbook=ScamPlaybook.UNKNOWN_SUSPICIOUS,
    contains_prompt_injection=False,
    confidence_level=Confidence.LOW,
)
