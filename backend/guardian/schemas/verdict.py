"""GuardianVerdict: the only verdict shape the API emits."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import AfterValidator, Field

from guardian.reason_codes import is_registered
from guardian.schemas.base import Strict
from guardian.schemas.enums import DecisionTierName


def must_be_registered(code: str) -> str:
    if not is_registered(code):
        raise ValueError(f"reason code is not in the registry: {code}")
    return code


ReasonCode = Annotated[
    str,
    Field(pattern=r"^RC_[A-Z0-9_]{3,40}$"),
    AfterValidator(must_be_registered),
]


class GuardianVerdict(Strict):
    decision_tier: DecisionTierName
    reason_codes: Annotated[list[ReasonCode], Field(min_length=1, max_length=6)]
    evidence_bullets: Annotated[list[Annotated[str, Field(max_length=160)]], Field(max_length=4)] = []
    system2_check_questions: Annotated[
        list[Annotated[str, Field(max_length=180)]], Field(max_length=2)
    ] = []
    cooling_off_seconds: Literal[0, 15, 30, 60, 300] = 0
    requires_user_account_confirm: bool = False
    allow_fast_unblock: bool = False
