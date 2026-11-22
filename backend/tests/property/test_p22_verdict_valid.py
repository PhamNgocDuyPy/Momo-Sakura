# Feature: momo-guardian-web, Property 22: Verdict luôn hợp lệ
"""Property 22: Verdict luôn hợp lệ.

**Validates: Requirements 6.12, 16.2, 16.3, 16.4**
"""

from __future__ import annotations

import re

from hypothesis import given
from hypothesis import strategies as st

from guardian.policy.composer import compose_verdict
from guardian.reason_codes import REGISTRY
from guardian.schemas.verdict import GuardianVerdict
from tests.property.strategies.signals import floorsets

_RC_PATTERN = re.compile(r"^RC_[A-Z0-9_]{3,40}$")
_PLAYBOOKS = st.none() | st.sampled_from(
    ["DEEPFAKE_RELATIVE_EMERGENCY", "IMPERSONATE_AUTHORITY_VNEID", "OTHER"]
)


@given(
    floors=floorsets(max_size=10).filter(lambda fs: len(list(fs)) >= 1),
    context_playbook=_PLAYBOOKS,
    extraction_playbook=_PLAYBOOKS,
    origin_ocr=st.booleans(),
    swap=st.booleans(),
)
def test_composed_verdict_is_always_valid(
    floors, context_playbook, extraction_playbook, origin_ocr, swap
) -> None:
    composed = compose_verdict(
        floors,
        context_playbook=context_playbook,
        extraction_playbook=extraction_playbook,
        origin_ocr=origin_ocr,
        account_swap_detected=swap,
    )
    verdict = composed.verdict
    GuardianVerdict.model_validate(verdict.model_dump())

    assert 1 <= len(verdict.reason_codes) <= 6
    assert len(set(verdict.reason_codes)) == len(verdict.reason_codes)
    for code in verdict.reason_codes:
        assert _RC_PATTERN.match(code)
        assert code in REGISTRY

    assert len(verdict.evidence_bullets) <= 4
    assert all(len(b) <= 160 for b in verdict.evidence_bullets)
    assert len(verdict.system2_check_questions) <= 2
    assert all(len(q) <= 180 for q in verdict.system2_check_questions)

    assert verdict.cooling_off_seconds in {0, 15, 30, 60, 300}
    assert verdict.cooling_off_seconds == floors.cooling_off_seconds()
    assert verdict.cooling_off_seconds == max(REGISTRY[f.reason_code].cooling_off for f in floors)
