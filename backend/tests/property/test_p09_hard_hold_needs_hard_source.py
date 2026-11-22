# Feature: momo-guardian-web, Property 9: HARD_HOLD cần nguồn HARD hợp lệ
"""Property 9: HARD_HOLD needs a valid HARD source.

**Validates: Requirements 11.4, 15.7, 17.6**
"""

from __future__ import annotations

import uuid

from hypothesis import given
from hypothesis import strategies as st

from guardian.control_plane.session import RequestContext
from guardian.llm.base import LLMResult
from guardian.llm.circuit_breaker import BreakerOutcome
from guardian.policy.engine import PolicyEngine
from guardian.providers.base import RecipientRisk
from guardian.reason_codes import REGISTRY
from guardian.schemas.enums import DecisionTier, HardSource, QrResult
from guardian.schemas.extraction import FALLBACK_EXTRACTION
from guardian.tools.url_checker import UrlCheckResult
from tests.property.strategies.extractions import extractions

engine = PolicyEngine(10)

_URL_FLAGS = ["APK_DOWNLOAD", "GOV_SPOOF", "RISKY_TLD", "PUNYCODE", "BRAND_LOOKALIKE", "SHORTENER", "IP_LITERAL"]
_FAIL_LLM = ["INVALID_SCHEMA", "REFUSAL", "TRUNCATED", "NO_TOOL_CALL", "ERROR", "NOT_IMPLEMENTED"]
_BREAKER_FAIL = ["TIMEOUT", "ERROR", "SKIPPED"]


def _ctx() -> RequestContext:
    return RequestContext.create(str(uuid.uuid4()), "FLOW_B", "secret")


def _assert_hard_sources_valid(ctx: RequestContext) -> None:
    if ctx.floors.final_tier != DecisionTier.HARD_HOLD:
        return
    hard = [f for f in ctx.floors if f.tier == DecisionTier.HARD_HOLD]
    assert hard, "HARD_HOLD without any HARD floor"
    for f in hard:
        assert isinstance(f.hard_source, HardSource)
        assert f.hard_source in REGISTRY[f.reason_code].hard_sources


@st.composite
def _llm_outcomes(draw):
    kind = draw(st.sampled_from(["ok", "llm_fail", "breaker_fail"]))
    if kind == "ok":
        ext = draw(extractions())
        return BreakerOutcome("OK", LLMResult(ext, "OK", "tool_use", 1), "closed", 1)
    if kind == "llm_fail":
        status = draw(st.sampled_from(_FAIL_LLM))
        return BreakerOutcome("OK", LLMResult(None, status, None, 1), "closed", 1)
    return BreakerOutcome(draw(st.sampled_from(_BREAKER_FAIL)), None, "closed", 1)


@given(
    score=st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
    hijack=st.booleans(),
    flag_sets=st.lists(st.sets(st.sampled_from(_URL_FLAGS)), max_size=3),
    outcome=st.none() | _llm_outcomes(),
    qr=st.none() | st.sampled_from(list(QrResult)),
    simo=st.booleans(),
    gnn=st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
    fan_in=st.integers(0, 30),
    ocr_confirm=st.booleans(),
)
def test_hard_hold_always_has_valid_hard_source(
    score, hijack, flag_sets, outcome, qr, simo, gnn, fan_in, ocr_confirm
) -> None:
    ctx = _ctx()
    engine.after_call("prompt_guard_cpu_score", score, ctx)
    engine.after_call("detect_hijack", hijack, ctx)
    engine.after_call(
        "check_urls", [UrlCheckResult("u", "d.com", "d.com", frozenset(s)) for s in flag_sets], ctx
    )
    if qr is not None:
        class _Qr:
            result = qr

        engine.after_call("verify_vietqr_emvco", _Qr(), ctx)
    engine.after_call(
        "lookup_recipient_risk_and_simo",
        RecipientRisk(simo_hit=simo, gnn_mule_score=gnn, fan_in_senders_per_hour=fan_in),
        ctx,
    )
    if outcome is not None:
        engine.after_call("quarantined_extract", outcome, ctx)
    _assert_hard_sources_valid(ctx)


@given(score=st.floats(min_value=0.0, max_value=1.0, allow_nan=False))
def test_prefilter_alone_never_exceeds_soft(score) -> None:
    ctx = _ctx()
    engine.after_call("prompt_guard_cpu_score", score, ctx)
    assert ctx.floors.final_tier <= DecisionTier.SOFT_FRICTION
    assert not any(f.tier == DecisionTier.HARD_HOLD for f in ctx.floors)


@given(
    score=st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
    failure=st.one_of(
        st.sampled_from(_FAIL_LLM).map(
            lambda s: BreakerOutcome("OK", LLMResult(None, s, None, 1), "closed", 1)
        ),
        st.sampled_from(_BREAKER_FAIL).map(lambda s: BreakerOutcome(s, None, "closed", 1)),
    ),
    heuristic=extractions(),
)
def test_llm_failure_and_fallback_heuristic_never_hard(score, failure, heuristic) -> None:
    ctx = _ctx()
    engine.after_call("prompt_guard_cpu_score", score, ctx)
    assert engine.apply_llm_outcome(ctx, failure) is None
    engine.apply_fallback_heuristic(ctx, heuristic)
    engine.apply_fallback_heuristic(ctx, FALLBACK_EXTRACTION)
    assert ctx.floors.final_tier <= DecisionTier.SOFT_FRICTION
    assert not any(f.tier == DecisionTier.HARD_HOLD for f in ctx.floors)
