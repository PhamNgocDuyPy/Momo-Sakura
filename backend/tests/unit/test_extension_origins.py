"""Task 23.1: Guardian_Extension origins are handled exactly like PASTE."""
from __future__ import annotations
import uuid
from collections.abc import AsyncIterator
from pathlib import Path
import httpx
import pytest
from guardian.config import Settings
from guardian.control_plane.flow_b import _ORIGIN_TO_ACCOUNT_ORIGIN
from guardian.main import create_app
from guardian.schemas.enums import AccountOrigin, ContentOrigin
HEADERS = {"X-Guardian-Session": str(uuid.uuid4())}
ORIGINS = ["EXTENSION_SELECTION", "EXTENSION_PAGE_TEXT"]
@pytest.fixture
async def client(tmp_path: Path) -> AsyncIterator[httpx.AsyncClient]:
    settings = Settings(
        _env_file=None,  # type: ignore[call-arg]
        llm_provider="mock",
        audit_log_path=str(tmp_path / "audit.jsonl"),
    )
    transport = httpx.ASGITransport(app=create_app(settings))
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as c:
        yield c
@pytest.mark.parametrize("origin", ORIGINS)
def test_origin_maps_to_paste_account_origin(origin: str) -> None:
    assert _ORIGIN_TO_ACCOUNT_ORIGIN[ContentOrigin(origin)] == AccountOrigin.PASTE
@pytest.mark.parametrize("origin", ORIGINS)
async def test_flow_b_accepts_extension_origin(client: httpx.AsyncClient, origin: str) -> None:
    r = await client.post(
        "/api/flow-b/check?stream=false",
        json={"content": {"origin": origin, "text": "Chiều nay đi cà phê nhé, 3h ở quán cũ."}},
        headers=HEADERS,
    )
    assert r.status_code == 200, r.text
    assert r.json()["verdict"]["decision_tier"] == "ALLOW"
@pytest.mark.parametrize("origin", ORIGINS)
async def test_selection_with_account_does_not_trigger_ocr_abort(client: httpx.AsyncClient, origin: str) -> None:
    r = await client.post(
        "/api/flow-b/check?stream=false",
        json={"content": {"origin": origin, "text": "ck 200k stk 0123456789 VCB nha"}},
        headers=HEADERS,
    )
    assert r.status_code == 200, r.text
    body = r.text
    assert "OCR_UNCONFIRMED" not in body
    assert "RC_OCR_ACCOUNT_NEEDS_CONFIRM" not in body
    assert "ABORT_WAIT_NAPAS_NAME_USER_CONFIRM" not in body
    assert r.json()["prefill"]["account_number"] == "0123456789"
@pytest.mark.parametrize("origin", ORIGINS)
async def test_extension_text_is_untrusted_like_paste(client: httpx.AsyncClient, origin: str) -> None:
    text = (
        "Đây là Công an quận 1, tài khoản VNeID của bạn liên quan đường dây rửa tiền, "
        "chuyển 50tr vào stk 1903777888999 TCB để xác minh, không được nói với ai"
    )
    r = await client.post(
        "/api/flow-b/check?stream=false", json={"content": {"origin": origin, "text": text}}, headers=HEADERS
    )
    assert r.status_code == 200, r.text
    assert r.json()["verdict"]["decision_tier"] == "HARD_HOLD"
    assert "RC_AUTHORITY_COERCION" in r.text
