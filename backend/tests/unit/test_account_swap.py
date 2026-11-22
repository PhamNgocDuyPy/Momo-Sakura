"""Task 25.2: account-change phrases, fallback heuristic and the System 2 question."""
from __future__ import annotations

import pytest

from guardian.llm.mock_rules import mock_extract
from guardian.policy.composer import compose_verdict
from guardian.control_plane.session import RequestContext
from guardian.reason_codes import REGISTRY, RC_ACCOUNT_SWAP_REQUEST
from guardian.schemas.enums import ContentMode, DecisionTier
from tests.unit.test_policy_engine_flow_b import ctx, engine

PHRASES = [
    "Chuyển gấp cho em 100k đi chị, em vừa mới đổi tài khoản nên chuyển vào tài khoản này nhé : 0378582085 tpbank",
    "em đổi số tài khoản rồi, ck 200k stk 0912345678 MB",
    "Gửi vào stk mới 0912345678 MB giúp em 300k",
    "ck 1tr vào tk mới 0912345678 VCB nhé",
    "Anh chuyển vào số tài khoản khác 0912345678 ACB",
    "Chị ơi em bị hack nick cũ, chuyển 500k vào 0912345678 MB",
    "Em mượn tạm tài khoản bạn, chuyển 2tr vào 0912345678 MB",
    "Anh chuyển qua tài khoản này giúp em nhé: 1234567890 VCB",
]

QUESTION = "Bạn đã gọi điện hoặc gọi video cho người này qua số điện thoại cũ để xác minh chưa?"


@pytest.mark.parametrize("text", PHRASES)
def test_mock_flags_account_change(text: str) -> None:
    ext = mock_extract(text, ContentMode.GENERAL)
    assert ext.payment_request is not None and ext.payment_request.requests_account_change


def test_plain_transfer_is_not_account_change() -> None:
    ext = mock_extract("ck 200k stk 0123456789 VCB nha", ContentMode.GENERAL)
    assert ext.payment_request is not None and not ext.payment_request.requests_account_change


@pytest.mark.parametrize("text", PHRASES)
def test_fallback_heuristic_adds_soft_account_swap(text: str) -> None:
    c: RequestContext = ctx()
    engine.apply_fallback_heuristic(c, mock_extract(text, ContentMode.GENERAL))
    assert RC_ACCOUNT_SWAP_REQUEST in {f.reason_code for f in c.floors}
    assert c.floors.final_tier == DecisionTier.SOFT_FRICTION


def test_account_swap_registry_and_question() -> None:
    spec = REGISTRY[RC_ACCOUNT_SWAP_REQUEST]
    assert spec.cooling_off == 30 and spec.min_tier == DecisionTier.SOFT_FRICTION and not spec.hard_sources
    assert "tài khoản mới" in spec.bullet_vi and len(spec.bullet_vi) <= 160
    c: RequestContext = ctx()
    engine.apply_fallback_heuristic(c, mock_extract(PHRASES[0], ContentMode.GENERAL))
    verdict = compose_verdict(c.floors, account_swap_detected=True).verdict
    assert QUESTION in verdict.system2_check_questions
    assert len(QUESTION) <= 180 and len(verdict.system2_check_questions) <= 2
    assert verdict.cooling_off_seconds == 30
    assert verdict.reason_codes[0] == RC_ACCOUNT_SWAP_REQUEST
