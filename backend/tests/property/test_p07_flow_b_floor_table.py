# Feature: momo-guardian-web, Property 7: Bảng floor tất định của Flow B
"""Property 7: every mapping row whose condition holds yields its floor in the FloorSet.

Drives the real ``PolicyEngine`` hooks in the Flow B order (after_call for QR / prefilter /
hijack / URLs / extraction, then before_emit_flow_b) over arbitrary signal combinations.

**Validates: Requirements 4.11, 4.12, 11.3, 11.6, 15.2, 15.4, 15.8**
"""
from __future__ import annotations

from types import SimpleNamespace

from hypothesis import given
from hypothesis import strategies as st

from guardian.control_plane.session import RequestContext
from guardian.policy import mapping
from guardian.policy.engine import PolicyEngine
from guardian.reason_codes import (
    REGISTRY,
    RC_CIRCULAR50_STRUCTURING_RISK,
    RC_PROMPT_INJECTION_BLOCKED,
    RC_SUSPECT_INJECTION_REVIEW,
    RC_UNOFFICIAL_APK_PHISHING,
    RC_VIETQR_FOREIGN_OR_NON_VND,
    RC_VIETQR_INVALID_FORMAT,
    RC_VIETQR_TAMPERED_BAD_CRC,
)
from guardian.schemas.enums import Cue, DecisionTier, QrResult, ScamPlaybook
from guardian.tools.url_checker import UrlCheckResult
from tests.property.strategies.extractions import extractions

SESSION = "123e4567-e89b-42d3-a456-426614174000"
THRESHOLD = mapping.PREFILTER_SOFT_THRESHOLD

_scores = st.one_of(
    st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
    st.sampled_from([0.0, 0.84, THRESHOLD, 0.86, 1.0]),
)
_url_flags = st.lists(
    st.sampled_from(
        ["APK_DOWNLOAD", "GOV_SPOOF", "RISKY_TLD", "PUNYCODE", "BRAND_LOOKALIKE", "SHORTENER", "IP_LITERAL"]
    ),
    max_size=4,
)
_amounts = st.one_of(
    st.integers(0, 30_000_000),
    st.sampled_from([8_999_999, 9_000_000, 9_999_999, 10_000_000]),
)
_totals = st.one_of(
    st.integers(0, 30_000_000),
    st.sampled_from([10_999_999, 11_000_000, 12_000_000]),
)


@given(
    qr=st.none() | st.sampled_from(list(QrResult)),
    score=_scores,
    hijack=st.booleans(),
    flag_lists=st.lists(_url_flags, max_size=3),
    extraction=extractions(),
    amount=st.none() | _amounts,
    total=_totals,
)
def test_p07_flow_b_floor_table(qr, score, hijack, flag_lists, extraction, amount, total) -> None:
    engine = PolicyEngine()
    ctx = RequestContext.create(SESSION, "WEB", "secret")

    if qr is not None:
        engine.after_call("verify_vietqr_emvco", SimpleNamespace(result=qr), ctx)
    engine.after_call("prompt_guard_cpu_score", score, ctx)
    engine.after_call("detect_hijack", hijack, ctx)
    urls = [UrlCheckResult("http://x", "x.example", "x.example", frozenset(f)) for f in flag_lists]
    engine.after_call("check_urls", urls, ctx)
    engine.apply_extraction(extraction, ctx)
    engine.before_emit_flow_b(ctx, extraction=extraction, amount_vnd=amount, total_24h_vnd=total)

    codes = {f.reason_code for f in ctx.floors}
    tier = ctx.floors.final_tier
    flags = {fl for fl_list in flag_lists for fl in fl_list}

    def has(code: str, at_least: DecisionTier) -> bool:
        return any(f.reason_code == code and f.tier >= at_least for f in ctx.floors)

    # Req 11.3 / 11.6: prefilter score alone raises SOFT.
    if score >= THRESHOLD:
        assert has(RC_SUSPECT_INJECTION_REVIEW, DecisionTier.SOFT_FRICTION)
        assert tier >= DecisionTier.SOFT_FRICTION
    # Req 15.2: injection or hijack -> HARD, cooling 60.
    if extraction.contains_prompt_injection or hijack:
        assert has(RC_PROMPT_INJECTION_BLOCKED, DecisionTier.HARD_HOLD)
        assert tier == DecisionTier.HARD_HOLD
        assert REGISTRY[RC_PROMPT_INJECTION_BLOCKED].cooling_off == 60
        assert ctx.floors.cooling_off_seconds() >= 60
    # URL APK / GOV spoof -> HARD.
    if flags & {"APK_DOWNLOAD", "GOV_SPOOF"}:
        assert has(RC_UNOFFICIAL_APK_PHISHING, DecisionTier.HARD_HOLD)
    # Req 15.4: structuring (cue or R5) -> SOFT.
    r5 = amount is not None and 9_000_000 <= amount < 10_000_000 and total + amount >= 20_000_000
    if Cue.SPLIT_TRANSFER_UNDER_10M in extraction.manipulation_cues or r5:
        assert has(RC_CIRCULAR50_STRUCTURING_RISK, DecisionTier.SOFT_FRICTION)
    # Req 15.8: any playbook other than NONE_DETECTED -> at least SOFT.
    if extraction.scam_playbook != ScamPlaybook.NONE_DETECTED:
        assert tier >= DecisionTier.SOFT_FRICTION
    # Req 4.11 / 4.12: QR classification.
    if qr == QrResult.BAD_CRC:
        assert has(RC_VIETQR_TAMPERED_BAD_CRC, DecisionTier.HARD_HOLD)
        assert tier == DecisionTier.HARD_HOLD
    elif qr == QrResult.FOREIGN_OR_NON_VND:
        assert has(RC_VIETQR_FOREIGN_OR_NON_VND, DecisionTier.SOFT_FRICTION)
    elif qr == QrResult.INVALID_FORMAT:
        assert has(RC_VIETQR_INVALID_FORMAT, DecisionTier.SOFT_FRICTION)
    assert codes <= set(REGISTRY)
