"""PlannerIntent: the only shape the privileged Planner may emit (design.md)."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import model_validator

from pydantic import Field

from guardian.schemas.base import Strict
from guardian.schemas.enums import (
    Confidence,
    Intent,
    SpendCategory,
    SpendMetric,
    SpendPeriod,
)


class TransferSlots(Strict):
    recipient_name: Annotated[str, Field(max_length=40)] | None = None
    amount_vnd: Annotated[int, Field(ge=0, le=100_000_000_000)] | None = None
    memo: Annotated[str, Field(max_length=60)] | None = None


class SpendSlots(Strict):
    category: SpendCategory = SpendCategory.ALL
    period: SpendPeriod = SpendPeriod.THIS_MONTH
    metric: SpendMetric = SpendMetric.TOTAL


class SplitSlots(Strict):
    participants_count: Annotated[int, Field(ge=2, le=20)] | None = None
    mode: Literal["EQUAL", "BY_ITEM"] | None = None


class PlannerIntent(Strict):
    intent: Intent
    transfer: TransferSlots | None = None
    spend: SpendSlots | None = None
    split: SplitSlots | None = None
    confidence_level: Confidence = Confidence.MEDIUM

    @model_validator(mode="after")
    def slots_match_intent(self) -> "PlannerIntent":
        """TRANSFER needs ``transfer``, SPEND_QUERY needs ``spend``; surplus slots are forbidden.

        ``split`` is optional for SPLIT_BILL (the mode may be implied by the opened screen).
        """
        if self.intent == Intent.TRANSFER and self.transfer is None:
            raise ValueError("intent TRANSFER requires the transfer slots")
        if self.intent == Intent.SPEND_QUERY and self.spend is None:
            raise ValueError("intent SPEND_QUERY requires the spend slots")
        if self.transfer is not None and self.intent != Intent.TRANSFER:
            raise ValueError("transfer slots are only allowed for intent TRANSFER")
        if self.spend is not None and self.intent != Intent.SPEND_QUERY:
            raise ValueError("spend slots are only allowed for intent SPEND_QUERY")
        if self.split is not None and self.intent != Intent.SPLIT_BILL:
            raise ValueError("split slots are only allowed for intent SPLIT_BILL")
        return self
