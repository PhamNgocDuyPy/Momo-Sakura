# Feature: momo-guardian-web, Property 8: LLM không hạ được tier
"""Property 8: whatever the (forced) QuarantinedExtraction is, Flow B's final tier is at least the
tier set by deterministic signals (SIMO, GNN >= 0.85, BAD_CRC, APK URL -> HARD_HOLD).

Drives the real endpoint with ``debug.force_llm_output`` (the T24 mechanism).

**Validates: Requirements 15.3, 15.6**
"""

from __future__ import annotations

import asyncio
import uuid
from typing import Any

import httpx
from hypothesis import given
from hypothesis import strategies as st

from guardian.main import create_app
from guardian.schemas.enums import DecisionTier
from guardian.schemas.extraction import QuarantinedExtraction
from guardian.tools.vietqr import encode_vietqr
from tests.conftest import make_settings
from tests.property.strategies.extractions import extractions

_APP = create_app(make_settings(guardian_debug=True))

_GOOD_QR = encode_vietqr("970407", "19033344455501", 500_000, "tien nha")
_BAD_QR = _GOOD_QR[:-4] + ("0000" if not _GOOD_QR.endswith("0000") else "1111")

# (text, qr_payload, origin): each one carries a deterministic HARD signal.
_HARD_SIGNALS = [
    ("Chuyển giúp mình nhé, stk 0909123456 MB", None, "PASTE"),  # SIMO hit
    ("Chuyển giúp mình nhé", _GOOD_QR, "QR_CAMERA"),  # GNN mule 0.91 + fan-in
    ("Chuyển giúp mình nhé", _BAD_QR, "QR_CAMERA"),  # BAD_CRC
    ("Tải app tại http://vneid-dichvu.example.com/app.apk ngay", None, "PASTE"),  # APK / gov spoof
]

BENIGN = QuarantinedExtraction(
    reasoning_summary="Tin nhắn bình thường.",
    scam_playbook="NONE_DETECTED",
    manipulation_cues=[],
    extracted_entities={},
    contains_prompt_injection=False,
    confidence_level="HIGH",
)


async def _check(text: str, qr: str | None, origin: str, forced: QuarantinedExtraction) -> dict[str, Any]:
    transport = httpx.ASGITransport(app=_APP)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/flow-b/check?stream=false",
            json={
                "content": {"origin": origin, "text": text, "qr_payload": qr},
                "debug": {"force_llm_output": forced.model_dump(mode="json")},
            },
            headers={"X-Guardian-Session": str(uuid.uuid4())},
        )
    assert resp.status_code == 200, resp.text
    return resp.json()


@given(signal=st.sampled_from(_HARD_SIGNALS), extraction=st.just(BENIGN) | extractions())
def test_p08_llm_cannot_downgrade_hard_signals(signal, extraction) -> None:
    text, qr, origin = signal
    data = asyncio.run(_check(text, qr, origin, extraction))
    assert data["verdict"]["decision_tier"] == "HARD_HOLD"
    assert data["verdict"]["reason_codes"]


@given(extraction=extractions())
def test_p08_llm_output_never_lowers_baseline(extraction) -> None:
    """Tier with any extraction is >= tier with the benign extraction, for a clean text."""
    base = asyncio.run(_check("Chiều nay đi cà phê nhé", None, "PASTE", BENIGN))
    other = asyncio.run(_check("Chiều nay đi cà phê nhé", None, "PASTE", extraction))
    assert DecisionTier[other["verdict"]["decision_tier"]] >= DecisionTier[base["verdict"]["decision_tier"]]
