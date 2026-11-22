# Feature: momo-guardian-web, Property 24: Không bao giờ hiển thị "100% an toàn"
"""Property 24: Không bao giờ hiển thị "100% an toàn".

Flow A, Flow B, context and fast-unblock all build their verdict through ``compose_verdict``; the
templates (reason-code bullets and System 2 questions) are monkeypatched to contain the phrase.

**Validates: Requirements 8.1**
"""

from __future__ import annotations

import dataclasses
import unicodedata
import uuid
from pathlib import Path
from unittest.mock import patch

from hypothesis import given, settings
from hypothesis import strategies as st

from guardian.config import Settings
from guardian.container import build_container
from guardian.policy import composer
from guardian.policy.composer import compose_verdict
from guardian.reason_codes import REGISTRY
from guardian.schemas.api_models import FlowBCheckRequest, FlowBContent
from guardian.schemas.enums import ContentOrigin
from tests.property.strategies.signals import floorsets

_PHRASES = ("100% an toàn", "100% safe")


@st.composite
def _injected(draw: st.DrawFn) -> str:
    phrase = draw(st.sampled_from(_PHRASES))
    phrase = "".join(c.upper() if draw(st.booleans()) else c.lower() for c in phrase)
    phrase = unicodedata.normalize(draw(st.sampled_from(["NFC", "NFD"])), phrase)
    prefix = draw(st.text(max_size=20))
    suffix = draw(st.text(max_size=20))
    return f"{prefix}{phrase}{suffix}"


def _forbidden(text: str) -> bool:
    folded = unicodedata.normalize("NFC", text).casefold()
    return any(p in folded for p in _PHRASES)


def _poisoned_registry(injected: str) -> dict[str, object]:
    return {
        code: dataclasses.replace(spec, bullet_vi=injected) for code, spec in REGISTRY.items()
    }


def _poisoned_questions(injected: str) -> dict[str, tuple[str, ...]]:
    return {
        key: (injected, f"{injected} ?")
        for key in (
            "DEEPFAKE_RELATIVE_EMERGENCY",
            "IMPERSONATE_AUTHORITY_VNEID",
            "OTHER",
            composer.GREY_ZONE_KEY,
        )
    }


def _assert_clean(verdict) -> None:
    for text in (*verdict.evidence_bullets, *verdict.system2_check_questions):
        assert not _forbidden(text)


@given(
    injected=_injected(),
    floors=floorsets(max_size=10).filter(lambda fs: len(list(fs)) >= 1),
    context_playbook=st.none() | st.sampled_from(["DEEPFAKE_RELATIVE_EMERGENCY", "OTHER"]),
    extraction_playbook=st.none() | st.sampled_from(["IMPERSONATE_AUTHORITY_VNEID", "OTHER"]),
)
def test_composer_strips_absolute_safety_claims(
    injected, floors, context_playbook, extraction_playbook
) -> None:
    with (
        patch.object(composer, "REGISTRY", _poisoned_registry(injected)),
        patch.object(composer, "SYSTEM2_QUESTIONS", _poisoned_questions(injected)),
    ):
        verdict = compose_verdict(
            floors, context_playbook=context_playbook, extraction_playbook=extraction_playbook
        ).verdict
    _assert_clean(verdict)
    assert verdict.evidence_bullets == []
    assert verdict.system2_check_questions == []


@settings(max_examples=10, deadline=None)
@given(injected=_injected())
def test_flow_b_response_has_no_absolute_safety_claim(injected) -> None:
    import asyncio
    import tempfile

    text = (
        "Đây là Công an quận 1, tài khoản VNeID của bạn liên quan đường dây rửa tiền, "
        "chuyển 50tr vào stk 1903777888999 TCB để xác minh, không được nói với ai"
    )
    with tempfile.TemporaryDirectory() as tmp:
        container = build_container(
            Settings(
                _env_file=None,  # type: ignore[call-arg]
                llm_provider="mock",
                audit_log_path=str(Path(tmp) / "audit.jsonl"),
            )
        )
        req = FlowBCheckRequest(content=FlowBContent(origin=ContentOrigin.PASTE, text=text))
        with (
            patch.object(composer, "REGISTRY", _poisoned_registry(injected)),
            patch.object(composer, "SYSTEM2_QUESTIONS", _poisoned_questions(injected)),
        ):
            result = asyncio.run(container.flow_b.check(str(uuid.uuid4()), req))
    verdict = result.response.verdict
    assert verdict.reason_codes
    _assert_clean(verdict)
