"""VerdictComposer: turns a FloorSet into a validated ``GuardianVerdict`` (design.md, "VerdictComposer").

All user-visible text comes from the reason-code registry and ``templates_vi``; nothing here reads
LLM free text.
"""

from __future__ import annotations

import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass, field

from pydantic import ValidationError

from guardian.policy.floors import FloorSet
from guardian.policy.templates_vi import ERRORS, SYSTEM2_QUESTIONS
from guardian.reason_codes import REGISTRY, RC_ACCOUNT_SWAP_REQUEST, RC_GREY_ZONE_RECIPIENT
from guardian.schemas.verdict import GuardianVerdict

MAX_REASON_CODES = 6
MAX_BULLETS = 4
MAX_QUESTIONS = 2
GREY_ZONE_KEY = "GREY_ZONE"
ACCOUNT_SWAP_KEY = "ACCOUNT_SWAP"
FORBIDDEN_PHRASES: tuple[str, ...] = ("100% an toàn", "100% safe")


class ComposerInvalid(Exception):
    """Composition produced an invalid verdict. Callers return 500 ``COMPOSER_INVALID`` and audit it."""

    error_code = "COMPOSER_INVALID"

    def __init__(self, detail: str = "") -> None:
        super().__init__(detail or ERRORS["COMPOSER_INVALID"])
        self.detail = detail


@dataclass(frozen=True)
class ComposedVerdict:
    verdict: GuardianVerdict
    overflow_reason_codes: tuple[str, ...] = field(default=())  # beyond the 6 shown; audit only


def _normalize(text: str) -> str:
    return unicodedata.normalize("NFC", text).casefold()


def passes_honesty(text: str) -> bool:
    """False when ``text`` claims absolute safety (checked after NFC, case-insensitive)."""
    folded = _normalize(text)
    return not any(_normalize(p) in folded for p in FORBIDDEN_PHRASES)


def ordered_reason_codes(floors: FloorSet) -> list[str]:
    """Unique reason codes sorted by (tier desc, registry priority asc)."""
    best: dict[str, int] = {}
    for floor in floors:
        best[floor.reason_code] = max(best.get(floor.reason_code, 0), int(floor.tier))
    return sorted(best, key=lambda code: (-best[code], REGISTRY[code].priority))


def select_questions(playbooks: Iterable[str | None], reason_codes: Iterable[str]) -> list[str]:
    """Up to 2 System 2 questions: context playbook, extraction playbook, then grey zone."""
    codes = set(reason_codes)
    keys = [p for p in playbooks if p]
    if RC_ACCOUNT_SWAP_REQUEST in codes:
        # The specific account-change question goes first; one question may still come from the playbook.
        keys.insert(0, ACCOUNT_SWAP_KEY)
    if RC_GREY_ZONE_RECIPIENT in codes:
        keys.append(GREY_ZONE_KEY)
    questions: list[str] = []
    for key in keys:
        for question in SYSTEM2_QUESTIONS.get(key, ()):
            if question not in questions:
                questions.append(question)
            if len(questions) == MAX_QUESTIONS:
                return questions
    return questions


def compose_verdict(
    floors: FloorSet,
    *,
    context_playbook: str | None = None,
    extraction_playbook: str | None = None,
    origin_ocr: bool = False,
    account_swap_detected: bool = False,
) -> ComposedVerdict:
    """Compose the verdict. Raises ``ComposerInvalid`` when the result fails ``GuardianVerdict``."""
    codes = ordered_reason_codes(floors)
    shown, overflow = codes[:MAX_REASON_CODES], codes[MAX_REASON_CODES:]
    bullets = [
        b for b in (REGISTRY[c].bullet_vi for c in shown[:MAX_BULLETS]) if passes_honesty(b)
    ]
    questions = [
        q
        for q in select_questions((context_playbook, extraction_playbook), shown)
        if passes_honesty(q)
    ]
    payload = {
        "decision_tier": floors.final_tier,
        "reason_codes": shown,
        "evidence_bullets": bullets,
        "system2_check_questions": questions,
        "cooling_off_seconds": floors.cooling_off_seconds(),
        "requires_user_account_confirm": origin_ocr or account_swap_detected,
        "allow_fast_unblock": floors.allow_fast_unblock(),
    }
    try:
        verdict = GuardianVerdict.model_validate(payload)
    except ValidationError as exc:
        raise ComposerInvalid(str(exc.error_count()) + " validation errors") from exc
    return ComposedVerdict(verdict=verdict, overflow_reason_codes=tuple(overflow))
