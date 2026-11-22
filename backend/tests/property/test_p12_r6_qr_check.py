# Feature: momo-guardian-web, Property 12: R6 – QR phải được kiểm tra trước khi ghép verdict
"""Property 12: R6 - a QR payload must be verified before the verdict is composed.

**Validates: Requirements 15.5**
"""

from __future__ import annotations

import asyncio
import uuid
from typing import Any

import httpx
from hypothesis import given
from hypothesis import strategies as st

from guardian.main import create_app
from guardian.tools.vietqr import encode_vietqr
from tests.conftest import make_settings
from tests.property.strategies.vietqr import vietqr_fields

STOP = "TEMPORAL_BYPASS_DETECTED_MISSING_VIETQR_CHECK"
_APP = create_app(make_settings(guardian_debug=True))

# Valid payloads, tampered payloads and arbitrary garbage: R6 must not depend on QR validity.
_payloads = st.one_of(
    vietqr_fields().map(lambda f: encode_vietqr(**f)),
    vietqr_fields().map(lambda f: encode_vietqr(**f)[:-1] + "0"),
    st.text(min_size=1, max_size=80),
)


async def _check(body: dict[str, Any]) -> dict[str, Any]:
    transport = httpx.ASGITransport(app=_APP)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/flow-a/check",
            json=body,
            headers={"X-Guardian-Session": str(uuid.uuid4())},
        )
    assert resp.status_code == 200, resp.text
    return resp.json()


@given(
    payload=_payloads,
    skip=st.booleans(),
    bank_bin=st.sampled_from(["970436", "970415", "970422"]),
    account=st.text(alphabet="0123456789", min_size=6, max_size=15),
    amount=st.integers(min_value=1_000, max_value=5_000_000),
)
def test_r6_missing_qr_check_is_hard_hold(
    payload: str, skip: bool, bank_bin: str, account: str, amount: int
) -> None:
    body: dict[str, Any] = {
        "bank_bin": bank_bin,
        "account_number": account,
        "amount_vnd": amount,
        "source_integrity": "VALID_VIETQR_CRC",
        "qr_payload": payload,
    }
    if skip:
        body["debug"] = {"simulate_skip_qr_verify": True}
    data = await_check(body)

    tools = [s["name"] for s in data["trace"] if s["kind"] == "tool"]
    bypass = STOP in data["stop_codes"]

    # Stop code appears iff the QR check was skipped.
    assert bypass == skip
    if skip:
        assert "verify_vietqr_emvco" not in tools
        assert data["verdict"]["decision_tier"] == "HARD_HOLD"
        assert "RC_QR_CHECK_BYPASS_DETECTED" in data["verdict"]["reason_codes"]
    else:
        assert tools and tools[0] == "verify_vietqr_emvco"


@given(amount=st.integers(min_value=1_000, max_value=5_000_000), skip=st.booleans())
def test_r6_not_applied_without_qr(amount: int, skip: bool) -> None:
    body: dict[str, Any] = {
        "bank_bin": "970436",
        "account_number": "0071000999888",
        "amount_vnd": amount,
        "source_integrity": "USER_TYPED",
    }
    if skip:
        body["debug"] = {"simulate_skip_qr_verify": True}
    assert STOP not in await_check(body)["stop_codes"]


def await_check(body: dict[str, Any]) -> dict[str, Any]:
    return asyncio.run(_check(body))
