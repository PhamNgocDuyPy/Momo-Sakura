"""Endpoint tests: /api/flow-b/check, /api/name/*, /api/debug/extract (task 13.3)."""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import httpx
import pytest

from guardian.config import Settings
from guardian.main import create_app
from guardian.tools.vietqr import encode_vietqr

HEADERS = {"X-Guardian-Session": str(uuid.uuid4())}
OCR_TEXT = "ck 200k vao stk 1012345678 VCB nha"
CLEAN = "Chiều nay đi cà phê nhé, 3h ở quán cũ."


def _make_client(tmp_path: Path, debug: bool) -> httpx.AsyncClient:
    settings = Settings(
        _env_file=None,  # type: ignore[call-arg]
        llm_provider="mock",
        guardian_debug=debug,
        audit_log_path=str(tmp_path / "audit.jsonl"),
    )
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=create_app(settings)), base_url="http://t")


@pytest.fixture
async def client(tmp_path: Path) -> AsyncIterator[httpx.AsyncClient]:
    async with _make_client(tmp_path, True) as c:
        yield c


@pytest.fixture
async def client_nodebug(tmp_path: Path) -> AsyncIterator[httpx.AsyncClient]:
    async with _make_client(tmp_path, False) as c:
        yield c


def _body(text: str | None = CLEAN, origin: str = "PASTE", qr: str | None = None, **extra: Any) -> dict[str, Any]:
    return {"content": {"origin": origin, "text": text, "qr_payload": qr}, **extra}


async def test_default_stream_is_ndjson_stage2_then_final(client: httpx.AsyncClient) -> None:
    r = await client.post("/api/flow-b/check", json=_body(), headers=HEADERS)
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/x-ndjson")
    events = [json.loads(line) for line in r.text.splitlines() if line]
    assert [e["event"] for e in events] == ["stage2", "final"]
    assert events[0]["provisional_tier"] in {"ALLOW", "SOFT_WARN", "HARD_HOLD"}
    assert events[1]["response"]["channel"] == "FLOW_B"


async def test_stream_false_returns_json(client: httpx.AsyncClient) -> None:
    r = await client.post("/api/flow-b/check?stream=false", json=_body(), headers=HEADERS)
    assert r.status_code == 200
    assert r.json()["channel"] == "FLOW_B"


async def test_red_alert_on_bad_crc(client: httpx.AsyncClient) -> None:
    good = encode_vietqr("970436", "1012345678", 100_000, "x")
    bad = good[:-4] + ("0000" if not good.endswith("0000") else "1111")
    r = await client.post("/api/flow-b/check", json=_body(None, "QR_CAMERA", bad), headers=HEADERS)
    stage2 = json.loads(r.text.splitlines()[0])
    assert stage2["event"] == "stage2"
    assert stage2["red_alert"] is True
    assert stage2["provisional_tier"] == "HARD_HOLD"


async def test_text_too_long_is_422(client: httpx.AsyncClient) -> None:
    r = await client.post("/api/flow-b/check", json=_body("a" * 4001), headers=HEADERS)
    assert r.status_code == 422
    assert r.json()["error"] == "CONTENT_TOO_LONG"


@pytest.mark.parametrize(
    "body",
    [_body(None), _body("   "), _body(None, "QR_CAMERA", "x" * 513), {"content": {"origin": "BOGUS", "text": "a"}}],
)
async def test_invalid_content_is_422(client: httpx.AsyncClient, body: dict[str, Any]) -> None:
    r = await client.post("/api/flow-b/check", json=body, headers=HEADERS)
    assert r.status_code == 422
    assert r.json()["error"] == "VALIDATION_ERROR"


async def test_missing_session_and_debug_gate(client_nodebug: httpx.AsyncClient) -> None:
    r = await client_nodebug.post("/api/flow-b/check", json=_body())
    assert r.status_code == 400
    r = await client_nodebug.post(
        "/api/flow-b/check", json=_body(debug={"simulate_llm_delay_ms": 10}), headers=HEADERS
    )
    assert r.status_code == 403
    assert r.json()["error"] == "DEBUG_DISABLED"


async def _ocr_pending(client: httpx.AsyncClient) -> dict[str, Any]:
    r = await client.post("/api/flow-b/check?stream=false", json=_body(OCR_TEXT, "OCR"), headers=HEADERS)
    assert r.status_code == 200
    data = r.json()
    assert data["verdict"]["reason_codes"][0] == "RC_OCR_ACCOUNT_NEEDS_CONFIRM"
    assert data["name_confirmation"] is not None
    return data["name_confirmation"]


async def test_name_inquiry_and_confirm_flow(client: httpx.AsyncClient) -> None:
    nc = await _ocr_pending(client)
    r = await client.post(
        "/api/name/inquiry",
        json={"pending_id": nc["pending_id"], "bank_bin": "970436", "account_number": "1012345678"},
        headers=HEADERS,
    )
    assert r.status_code == 200
    assert r.json()["pending_id"] == nc["pending_id"]
    assert r.json()["account_digits_spaced"] == "1 0 1 2 3 4 5 6 7 8"

    r = await client.post(
        "/api/name/confirm", json={"pending_id": nc["pending_id"], "confirmed": True}, headers=HEADERS
    )
    assert r.status_code == 200
    out = r.json()
    assert out["source_integrity"] == "OCR_CONFIRMED_BY_USER"
    assert out["confirmation_token"].startswith("ct_")
    assert out["check"]["channel"] == "FLOW_B"
    assert "RC_OCR_ACCOUNT_NEEDS_CONFIRM" not in out["check"]["verdict"]["reason_codes"]


async def test_flow_a_ocr_abort_returns_name_confirmation_then_token_unlocks(
    client: httpx.AsyncClient,
) -> None:
    body = {
        "bank_bin": "970436",
        "account_number": "1012345678",
        "amount_vnd": 150_000,
        "source_integrity": "OCR_UNCONFIRMED",
    }
    r = await client.post("/api/flow-a/check", json=body, headers=HEADERS)
    assert r.status_code == 200
    nc = r.json()["name_confirmation"]
    assert nc["pending_id"].startswith("pc_")
    c = await client.post(
        "/api/name/confirm", json={"pending_id": nc["pending_id"], "confirmed": True}, headers=HEADERS
    )
    token = c.json()["confirmation_token"]
    r2 = await client.post(
        "/api/flow-a/check",
        json={**body, "source_integrity": "OCR_CONFIRMED_BY_USER", "confirmation_token": token},
        headers=HEADERS,
    )
    assert r2.json()["name_confirmation"] is None


async def test_name_confirm_false_stays_unconfirmed(client: httpx.AsyncClient) -> None:
    nc = await _ocr_pending(client)
    r = await client.post(
        "/api/name/confirm", json={"pending_id": nc["pending_id"], "confirmed": False}, headers=HEADERS
    )
    assert r.json() == {"confirmation_token": None, "source_integrity": "OCR_UNCONFIRMED", "check": None}


async def test_name_unknown_pending_is_404_and_other_session_denied(client: httpx.AsyncClient) -> None:
    r = await client.post("/api/name/confirm", json={"pending_id": "pc_x", "confirmed": True}, headers=HEADERS)
    assert r.status_code == 404
    nc = await _ocr_pending(client)
    other = {"X-Guardian-Session": str(uuid.uuid4())}
    r = await client.post(
        "/api/name/confirm", json={"pending_id": nc["pending_id"], "confirmed": True}, headers=other
    )
    assert r.status_code == 404


async def test_debug_extract(client: httpx.AsyncClient, client_nodebug: httpx.AsyncClient) -> None:
    r = await client.post("/api/debug/extract", json={"text": CLEAN}, headers=HEADERS)
    assert r.status_code == 200
    data = r.json()
    assert data["llm_status"] == "OK"
    assert "reasoning_summary" in data["extraction"]
    r = await client_nodebug.post("/api/debug/extract", json={"text": CLEAN}, headers=HEADERS)
    assert r.status_code == 404
