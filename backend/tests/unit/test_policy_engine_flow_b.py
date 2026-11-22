"""Unit tests for PolicyEngine Flow B rules (task 12.1)."""
from __future__ import annotations

import uuid

from guardian.control_plane.tool_runner import Abort, Allow
from guardian.control_plane.session import RequestContext
from guardian.llm.base import LLMResult
from guardian.llm.circuit_breaker import BreakerOutcome
from guardian.policy.engine import PII_EGRESS_ABORTED, PolicyEngine
from guardian.providers.base import Contact
from guardian.reason_codes import (
    RC_BANK_COACHING_DETECTED,
    RC_LLM_OUTPUT_INVALID,
    RC_LLM_TIMEOUT_FALLBACK,
    RC_LLM_UNAVAILABLE_FALLBACK,
    RC_MANIPULATION_CUE_REVIEW,
    RC_NO_SCAM_SIGNAL_FOUND,
    RC_PII_EGRESS_BLOCKED,
    RC_PROMPT_INJECTION_BLOCKED,
    RC_REMOTE_SCREEN_TAKEOVER,
    RC_RISKY_URL_DETECTED,
    RC_SUSPECT_INJECTION_REVIEW,
    RC_SUSPICIOUS_UNCLASSIFIED,
    RC_UNOFFICIAL_APK_PHISHING,
    RC_AUTHORITY_COERCION,
    RC_ACCOUNT_SWAP_REQUEST,
    RC_CIRCULAR50_STRUCTURING_RISK,
)
from guardian.schemas.enums import Confidence, Cue, DecisionTier, ScamPlaybook, StopCode
from guardian.schemas.extraction import PaymentRequest, QuarantinedExtraction
from guardian.tools.pii import contact_name_variants, redact_pii_local
from guardian.tools.url_checker import UrlCheckResult


class FakeWallet:
    def contacts(self) -> list[Contact]:
        return [Contact(id="c1", bank_bin="970436", account_number="0071000111222", display_name="Nguyễn Văn Minh", aliases=["Minh"])]


engine = PolicyEngine(10, wallet=FakeWallet())  # type: ignore[arg-type]


def ctx() -> RequestContext:
    return RequestContext.create(str(uuid.uuid4()), "FLOW_B", "secret")


def codes(c: RequestContext) -> set[str]:
    return {f.reason_code for f in c.floors}


def ext(playbook=ScamPlaybook.NONE_DETECTED, cues=(), injection=False, **kw) -> QuarantinedExtraction:
    return QuarantinedExtraction(
        reasoning_summary="t",
        scam_playbook=playbook,
        manipulation_cues=list(cues),
        contains_prompt_injection=injection,
        confidence_level=Confidence.HIGH,
        **kw,
    )


def test_egress_blocks_pii_and_uses_contact_names() -> None:
    c = ctx()
    d = engine.before_call("quarantined_extract", {"text": "gui CCCD 012345678901"}, c)
    assert isinstance(d, Abort) and d.result_code == PII_EGRESS_ABORTED
    assert d.stop_code == StopCode.PII_EGRESS_BLOCKED
    assert codes(c) == {RC_PII_EGRESS_BLOCKED}
    assert c.floors.final_tier == DecisionTier.SOFT_FRICTION

    # A bare contact name is PII; redacting with the same variants makes egress pass.
    raw = "tra tien cho Minh nhe"
    assert isinstance(engine.before_call("quarantined_extract", {"text": raw}, ctx()), Abort)
    names = contact_name_variants(FakeWallet().contacts())
    redacted, _ = redact_pii_local(raw, contact_names=names)
    assert isinstance(engine.before_call("quarantined_extract", {"text": redacted}, ctx()), Allow)


def test_prefilter_hijack_urls() -> None:
    c = ctx()
    engine.apply_prefilter(0.9, c)
    assert codes(c) == {RC_SUSPECT_INJECTION_REVIEW}
    assert c.floors.final_tier == DecisionTier.SOFT_FRICTION
    engine.after_call("detect_hijack", True, c)
    assert c.floors.final_tier == DecisionTier.HARD_HOLD

    c2 = ctx()
    engine.after_call("check_urls", [UrlCheckResult("u", "a.top", "a.top", frozenset({"RISKY_TLD"}))], c2)
    assert codes(c2) == {RC_RISKY_URL_DETECTED}
    engine.after_call("check_urls", [UrlCheckResult("u", "b.com", "b.com", frozenset({"APK_DOWNLOAD"}))], c2)
    assert RC_UNOFFICIAL_APK_PHISHING in codes(c2) and c2.floors.final_tier == DecisionTier.HARD_HOLD


def test_cues_never_hard_without_hard_playbook() -> None:
    c = ctx()
    engine.apply_extraction(
        ext(ScamPlaybook.UNKNOWN_SUSPICIOUS, [Cue.COACHING_WHAT_TO_TELL_BANK, Cue.SCREEN_SHARE_OR_REMOTE_APP]), c
    )
    assert codes(c) == {RC_SUSPICIOUS_UNCLASSIFIED, RC_MANIPULATION_CUE_REVIEW}
    assert c.floors.final_tier == DecisionTier.SOFT_FRICTION

    c = ctx()
    engine.apply_extraction(
        ext(
            ScamPlaybook.IMPERSONATE_AUTHORITY_VNEID,
            [Cue.COACHING_WHAT_TO_TELL_BANK, Cue.SCREEN_SHARE_OR_REMOTE_APP, Cue.SPLIT_TRANSFER_UNDER_10M],
        ),
        c,
    )
    assert {RC_AUTHORITY_COERCION, RC_BANK_COACHING_DETECTED, RC_REMOTE_SCREEN_TAKEOVER, RC_CIRCULAR50_STRUCTURING_RISK} <= codes(c)
    assert RC_MANIPULATION_CUE_REVIEW not in codes(c)
    assert c.floors.final_tier == DecisionTier.HARD_HOLD


def test_injection_extraction_is_hard() -> None:
    c = ctx()
    engine.apply_extraction(ext(injection=True), c)
    assert codes(c) == {RC_PROMPT_INJECTION_BLOCKED}
    assert c.floors.final_tier == DecisionTier.HARD_HOLD


def test_llm_outcomes() -> None:
    def res(status):
        return LLMResult(value=None, status=status, raw_stop_reason=None, latency_ms=1)

    c = ctx()
    assert engine.apply_llm_outcome(c, BreakerOutcome("TIMEOUT", None, "closed", 4000)) is None
    assert codes(c) == {RC_LLM_TIMEOUT_FALLBACK}
    c = ctx()
    engine.apply_llm_outcome(c, BreakerOutcome("SKIPPED", None, "open", 0))
    assert codes(c) == {RC_LLM_UNAVAILABLE_FALLBACK}
    c = ctx()
    engine.apply_llm_outcome(c, res("NOT_IMPLEMENTED"))
    assert codes(c) == {RC_LLM_UNAVAILABLE_FALLBACK}
    c = ctx()
    engine.after_call("quarantined_extract", BreakerOutcome("OK", res("INVALID_SCHEMA"), "closed", 5), c)
    assert codes(c) == {RC_LLM_OUTPUT_INVALID, RC_SUSPICIOUS_UNCLASSIFIED}
    assert c.floors.final_tier == DecisionTier.SOFT_FRICTION

    c = ctx()
    good = ext(ScamPlaybook.TASK_SCAM_JOB_ONLINE)
    out = engine.apply_llm_outcome(c, BreakerOutcome("OK", LLMResult(good, "OK", "tool_use", 3), "closed", 3))
    assert out == good and c.floors.final_tier == DecisionTier.HARD_HOLD


def test_fallback_heuristic_caps_at_soft() -> None:
    c = ctx()
    engine.apply_fallback_heuristic(
        c, ext(ScamPlaybook.IMPERSONATE_AUTHORITY_VNEID, [Cue.COACHING_WHAT_TO_TELL_BANK, Cue.URGENCY_TIME_PRESSURE])
    )
    assert codes(c) == {RC_SUSPICIOUS_UNCLASSIFIED, RC_MANIPULATION_CUE_REVIEW}
    assert c.floors.final_tier == DecisionTier.SOFT_FRICTION


def test_emit_p10_x1() -> None:
    c = ctx()
    engine.before_emit_flow_b(c, extraction=ext())
    assert codes(c) == {RC_NO_SCAM_SIGNAL_FOUND}

    c = ctx()
    engine.apply_prefilter(0.95, c)
    engine.before_emit_flow_b(c, extraction=ext())
    assert RC_NO_SCAM_SIGNAL_FOUND not in codes(c)

    c = ctx()
    pr = PaymentRequest(account_digits_raw="1111111111")
    swap = engine.before_emit_flow_b(
        c, extraction=ext(payment_request=pr), linked_account_digits="2222222222"
    )
    assert swap and RC_ACCOUNT_SWAP_REQUEST in codes(c) and RC_NO_SCAM_SIGNAL_FOUND not in codes(c)

    c = ctx()
    assert engine.before_emit_flow_b(c, extraction=None) is False
    assert not codes(c)
