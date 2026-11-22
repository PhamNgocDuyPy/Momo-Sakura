# Feature: momo-guardian-web, Property 11: R2 – tài khoản OCR chưa xác nhận
"""Property 11: R2 for unconfirmed OCR accounts (Flow A without token, Flow B origin OCR).

**Validates: Requirements 9.1, 9.2, 9.5, 9.6, 9.7**
"""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

from hypothesis import given
from hypothesis import strategies as st

from guardian.config import Settings
from guardian.container import build_container
from guardian.schemas.api_models import FlowACheckRequest, FlowBCheckRequest, FlowBContent
from guardian.schemas.enums import ContentOrigin, SourceIntegrity, StopCode
from tests.property.strategies.vietqr import accounts, valid_bins

SESSION = "6f1c1d0e-7a3b-4c52-9d4e-0a1b2c3d4e5f"
_AUDIT = Path(tempfile.mkdtemp(prefix="p11_")) / "audit.jsonl"
_CONTAINER = build_container(
    Settings(_env_file=None, llm_provider="mock", guardian_debug=False, audit_log_path=str(_AUDIT))
)
_RISK_TOOL = "lookup_recipient_risk_and_simo"
_BANKS = ["Vietcombank", "Techcombank", "MB Bank", "ACB", "BIDV", "VPBank"]


def _assert_r2(response) -> None:
    for step in response.trace:
        if step.name == _RISK_TOOL:
            assert step.status == "aborted"
            assert step.detail.get("result") == "UNCONFIRMED_ACCOUNT_ABORTED"
    assert not any(s.name == _RISK_TOOL and s.status == "ok" for s in response.trace)
    assert StopCode.ABORT_WAIT_NAPAS_NAME_USER_CONFIRM.value in [
        getattr(c, "value", c) for c in response.stop_codes
    ]
    assert response.verdict.requires_user_account_confirm is True


@given(
    bank_bin=valid_bins,
    account=accounts,
    amount=st.integers(min_value=1, max_value=50_000_000),
    claimed=st.sampled_from([SourceIntegrity.OCR_UNCONFIRMED, SourceIntegrity.OCR_CONFIRMED_BY_USER]),
    token=st.one_of(st.none(), st.text(min_size=1, max_size=20)),
)
def test_flow_a_unconfirmed_ocr_is_aborted(bank_bin, account, amount, claimed, token) -> None:
    req = FlowACheckRequest(
        bank_bin=bank_bin,
        account_number=account,
        amount_vnd=amount,
        source_integrity=claimed,
        confirmation_token=token,  # never issued by /api/name/confirm, so never valid
    )
    result = asyncio.run(_CONTAINER.flow_a.check(SESSION, req))
    _assert_r2(result.response)


@given(
    bank=st.sampled_from(_BANKS),
    account=accounts,
    amount=st.integers(min_value=1, max_value=50_000_000),
)
def test_flow_b_ocr_origin_is_aborted(bank, account, amount) -> None:
    text = f"Chuyển khoản {amount} đến {bank} STK {account}"
    req = FlowBCheckRequest(content=FlowBContent(origin=ContentOrigin.OCR, text=text))
    result = asyncio.run(_CONTAINER.flow_b.check(SESSION, req))
    _assert_r2(result.response)
