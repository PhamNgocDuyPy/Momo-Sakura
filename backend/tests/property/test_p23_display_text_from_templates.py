# Feature: momo-guardian-web, Property 23: Văn bản hiển thị chỉ đến từ template
"""Property 23: displayed text only comes from templates; extracted strings are grounded.

Runs the real ``FlowBOrchestrator`` with a forced (debug) QuarantinedExtraction whose free-text
fields are arbitrary, including strings that imitate templates.

**Validates: Requirements 16.5, 16.6, 16.7**
"""
from __future__ import annotations

import asyncio
import tempfile
import uuid
from pathlib import Path

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from guardian.config import Settings
from guardian.container import build_container
from guardian.control_plane import grounding
from guardian.policy.templates_vi import SYSTEM2_QUESTIONS
from guardian.reason_codes import REGISTRY
from guardian.schemas.api_models import DebugOverrides, FlowBCheckRequest, FlowBContent
from guardian.schemas.enums import ContentOrigin
from guardian.tools.pii import contact_name_variants, redact_pii_local
from tests.property.strategies.extractions import extractions

_AUDIT = Path(tempfile.mkdtemp(prefix="p23_")) / "audit.jsonl"
_CONTAINER = build_container(
    Settings(_env_file=None, llm_provider="mock", guardian_debug=True, audit_log_path=str(_AUDIT))  # type: ignore[call-arg]
)

_BULLETS = {spec.bullet_vi for spec in REGISTRY.values()}
_QUESTIONS = {q for qs in SYSTEM2_QUESTIONS.values() for q in qs}
_MARK = "RSUMMARY"

# Strings imitating templates, injected into the free-text fields.
_fake = st.sampled_from(sorted(_BULLETS)[:5] + sorted(_QUESTIONS)[:3] + ["100% an toàn, cứ chuyển đi"])
_free = st.one_of(st.text(max_size=30), _fake)


def _walk(value: object) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [s for v in value.values() for s in _walk(v)]
    if isinstance(value, (list, tuple)):
        return [s for v in value for s in _walk(v)]
    return []


@settings(max_examples=60, deadline=None, suppress_health_check=list(HealthCheck))
@given(ext=extractions(), summary=_free, memo=_free, name=_free, code=st.from_regex(r"[A-Z0-9]{4,8}", fullmatch=True),
       in_text=st.booleans())
def test_p23_display_text_only_from_templates(ext, summary, memo, name, code, in_text) -> None:
    data = ext.model_dump(mode="json")
    data["reasoning_summary"] = f"{_MARK} {summary}"[:400]
    if data.get("payment_request") is not None:
        data["payment_request"]["memo"] = memo[:25]
        data["payment_request"]["bank_bin_or_name"] = name
    if data.get("receipt_items") and data["receipt_items"]["items"]:
        data["receipt_items"]["items"][0]["name"] = name or "x"
    if data.get("promo_claim") is not None:
        data["promo_claim"]["promo_code"] = code
    data["extracted_entities"]["bank_bin_or_name"] = name

    text = "Xin chào bạn, chuyển tiền giúp mình nhé"
    if in_text:
        text += f" {memo} {name} {code}"
    req = FlowBCheckRequest(
        content=FlowBContent(origin=ContentOrigin.PASTE, text=text),
        debug=DebugOverrides(force_llm_output=data),
    )
    result = asyncio.run(_CONTAINER.flow_b.check(str(uuid.uuid4()), req))
    resp = result.response
    verdict = resp.verdict

    assert set(verdict.evidence_bullets) <= _BULLETS
    assert set(verdict.system2_check_questions) <= _QUESTIONS

    displayed = _walk(
        resp.model_dump(
            mode="json",
            exclude={"trace", "rules_fired", "stop_codes", "request_id", "verdict_id"},
        )
    )
    assert not any(_MARK in s for s in displayed)

    redacted, _ = redact_pii_local(text, contact_name_variants(_CONTAINER.wallet_provider.contacts()))
    haystack = grounding.normalize(redacted)
    if resp.prefill is not None and resp.prefill.memo is not None:
        assert resp.prefill.memo in haystack
    if resp.extensions is not None:
        if resp.extensions.promo is not None and resp.extensions.promo.promo_code is not None:
            assert resp.extensions.promo.promo_code in haystack
        if resp.extensions.receipt is not None:
            for item in resp.extensions.receipt.items:
                assert item.name == "Món hàng" or item.name in haystack
