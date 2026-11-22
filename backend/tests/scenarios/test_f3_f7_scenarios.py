"""F3 (A06), F7 (A11, A12) scenarios plus Bill_Splitter, Bill_Monitor and /api/qr/encode checks.

The split router is included here when ``guardian.main`` does not register it yet.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi import FastAPI

from eval.scenario_loader import REPO_ROOT, Scenario, load_scenarios
from guardian.api import split as split_api
from guardian.main import create_app as _create_app
from tests.scenarios import runner
from tests.scenarios.runner import make_settings, run_scenario

IDS = ["A06", "A11", "A12"]
SCENARIOS: dict[str, Scenario] = {s.id: s for s in load_scenarios() if s.id in IDS}
FIXTURE_DIR = REPO_ROOT / "fixtures"

HARD_ACCOUNT = {"bank_bin": "970407", "account_number": "19033344455501", "amount_vnd": 500000}
ALLOW_ACCOUNT = {"bank_bin": "970436", "account_number": "1012345678", "amount_vnd": 150000}
SOFT_ACCOUNT = {"bank_bin": "970418", "account_number": "21410000123456", "amount_vnd": 150000}


def build_app(settings: Any = None) -> FastAPI:
    app = _create_app(settings or make_settings())
    if not any(getattr(r, "path", "") == "/api/split/compute" for r in app.routes):
        app.include_router(split_api.router)
    return app


@pytest.fixture(autouse=True)
def _app_with_split(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setattr(runner, "create_app", build_app, raising=False)  # runner imports create_app lazily
    yield


def test_fixtures_present() -> None:
    assert sorted(SCENARIOS) == IDS
    assert len(SCENARIOS["A06"].cases) == 3


@pytest.mark.parametrize("scenario_id", IDS)
async def test_scenario(scenario_id: str) -> None:
    result = await run_scenario(SCENARIOS[scenario_id])
    problems = [(c.endpoint, c.status_code, c.mismatches) for c in result.cases if not c.passed]
    assert not problems, problems


def test_a06_receipt_text_matches_fixture_file() -> None:
    text = (FIXTURE_DIR / "receipts" / "lau_3_nguoi.txt").read_text(encoding="utf-8")
    case = SCENARIOS["A06"].cases[0]
    assert case.request["content"]["text"].strip() == text.strip()


def test_a11_a12_alert_set_is_exact() -> None:
    wallet = json.loads(Path(FIXTURE_DIR / "wallet_sandbox.json").read_text(encoding="utf-8"))
    assert {b["provider_id"] for b in wallet["bills"]} == {"EVN_HCMC", "SAWACO", "FPT_INTERNET"}


# ----------------------------------------------------------------- helpers


async def _client(app: FastAPI) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


def _headers(session: str | None = None) -> dict[str, str]:
    return {"X-Guardian-Session": session or str(uuid.uuid4())}


def _split_body(**over: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "items": [
            {"name": "A", "quantity": 1, "unit_price_vnd": 100},
            {"name": "B", "quantity": 2, "unit_price_vnd": 50},
        ],
        "receipt_total_vnd": 200,
        "participants": [{"id": "p1", "display_name": "Ban"}, {"id": "p2", "display_name": "Minh"}],
        "mode": "BY_ITEM",
    }
    body.update(over)
    return body


# ----------------------------------------------------------------- split


async def test_split_by_item_conserves_and_unassigned_is_422() -> None:
    async with await _client(build_app()) as c:
        h = _headers()
        ok = await c.post(
            "/api/split/compute",
            json=_split_body(
                assignments=[
                    {"item_index": 0, "participant_ids": ["p1", "p2"]},
                    {"item_index": 1, "participant_ids": ["p2"]},
                ]
            ),
            headers=h,
        )
        assert ok.status_code == 200, ok.text
        assert [s["amount_vnd"] for s in ok.json()["shares"]] == [50, 150]

        missing = await c.post(
            "/api/split/compute",
            json=_split_body(assignments=[{"item_index": 0, "participant_ids": ["p1"]}]),
            headers=h,
        )
        assert missing.status_code == 422
        assert missing.json()["error"] == "UNASSIGNED_ITEMS"

        too_many = await c.post(
            "/api/split/compute",
            json=_split_body(
                participants=[{"id": f"p{i}", "display_name": "x"} for i in range(21)],
                mode="EQUAL",
            ),
            headers=h,
        )
        assert too_many.status_code == 422


async def test_split_requires_session() -> None:
    async with await _client(build_app()) as c:
        r = await c.post("/api/split/compute", json=_split_body(mode="EQUAL"))
        assert r.status_code == 400
        assert r.json()["error"] == "SESSION_REQUIRED"


# ----------------------------------------------------------------- bill monitor


def test_bill_monitor_boundaries() -> None:
    from datetime import date, datetime, timedelta, timezone

    from guardian.features.bill_monitor import alerts
    from guardian.providers.base import BillRecord, Subscription

    tz = timezone(timedelta(hours=7))
    now = datetime(2026, 11, 30, 20, 0, tzinfo=tz)

    def bills(amounts: list[int]) -> list[BillRecord]:
        return [
            BillRecord(
                provider_id="P",
                provider_name="P",
                period=f"2026-{i + 1:02d}",
                amount_vnd=a,
                due_date=date(2026, i + 1, 5),
                status="PAID",
            )
            for i, a in enumerate(amounts)
        ]

    assert alerts(bills([100, 100, 100, 130]), [], now)  # exactly +30% triggers
    assert not alerts(bills([100, 100, 100, 129]), [], now)
    assert not alerts(bills([100, 100, 1000]), [], now)  # fewer than 3 previous periods

    def sub(sid: str, renew: date, used: datetime | None) -> Subscription:
        return Subscription(id=sid, name=sid, amount_vnd=1, renewal_date=renew, last_used_at=used)

    subs = [
        sub("in7", date(2026, 12, 7), now),
        sub("in8", date(2026, 12, 8), now),
        sub("today", date(2026, 11, 30), now),
        sub("past", date(2026, 11, 29), now),
        sub("u30", date(2027, 6, 1), now - timedelta(days=30)),
        sub("u29", date(2027, 6, 1), now - timedelta(days=29, hours=23)),
    ]
    out = alerts([], subs, now)
    renew = {a.subscription_id for a in out if a.type == "RENEWAL_SOON"}
    unused = {a.subscription_id for a in out if a.type == "UNUSED_SUBSCRIPTION"}
    assert renew == {"in7", "today"}
    assert unused == {"u30"}


# ----------------------------------------------------------------- /api/qr/encode


async def _verdict(c: httpx.AsyncClient, h: dict[str, str], tx: dict[str, Any]) -> str:
    r = await c.post("/api/flow-a/check", json=tx, headers=h)
    assert r.status_code == 200, r.text
    return str(r.json()["verdict_id"])


def _encode_body(verdict_id: str | None, **over: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "purpose": "BANK_HANDOFF",
        "verdict_id": verdict_id,
        "bank_bin": "970436",
        "account_number": "1012345678",
        "amount_vnd": 150000,
        "memo": "Tiền cơm",
    }
    body.update(over)
    return body


async def test_encode_hard_hold_is_denied_and_audited(tmp_path: Path) -> None:
    audit = tmp_path / "audit.jsonl"
    app = build_app(make_settings(audit_log_path=str(audit)))
    async with await _client(app) as c:
        h = _headers()
        vid = await _verdict(c, h, HARD_ACCOUNT)
        r = await c.post("/api/qr/encode", json=_encode_body(vid), headers=h)
        assert r.status_code == 403
        assert r.json()["error"] == "HANDOFF_BLOCKED_HARD_HOLD"
        # Unknown verdict, missing verdict and another session's verdict are denied too.
        for body, hh in (
            (_encode_body("vd_unknown"), h),
            (_encode_body(None), h),
            (_encode_body(vid), _headers()),
        ):
            denied = await c.post("/api/qr/encode", json=body, headers=hh)
            assert denied.status_code == 403
            assert denied.json()["error"] == "HANDOFF_BLOCKED_HARD_HOLD"
    records = [json.loads(x) for x in audit.read_text(encoding="utf-8").splitlines()]
    denied_records = [x for x in records if x.get("event") == "HANDOFF_DENIED"]
    assert len(denied_records) == 4
    assert "session_id" not in json.dumps(denied_records)


async def test_encode_soft_needs_cooldown_then_ok() -> None:
    app = build_app()
    async with await _client(app) as c:
        h = _headers()
        vid = await _verdict(c, h, SOFT_ACCOUNT)
        assert (await c.post("/api/qr/encode", json=_encode_body(vid), headers=h)).status_code == 409
        app.state.container.verdict_store.mark_cooldown_completed(vid)
        r = await c.post("/api/qr/encode", json=_encode_body(vid), headers=h)
        assert r.status_code == 200, r.text


async def test_encode_allow_returns_valid_payload_and_no_deeplink() -> None:
    from guardian.tools.vietqr import verify_vietqr_emvco

    async with await _client(build_app()) as c:
        h = _headers()
        vid = await _verdict(c, h, ALLOW_ACCOUNT)
        r = await c.post("/api/qr/encode", json=_encode_body(vid), headers=h)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["verify"]["result"] == "VALID_VIETQR"
        assert body["deeplink"] is None
        fields = verify_vietqr_emvco(body["payload"]).fields
        assert fields is not None
        assert fields["account_number"] == "1012345678"
        assert fields["amount_vnd"] == 150000
        assert fields["tag62"]["purpose"] == "Tien com"  # memo folded to ASCII


async def test_encode_split_bill_needs_no_verdict_and_deeplink_from_template(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from guardian.tools import banks

    bank = banks.bank_by_bin("970436")
    assert bank is not None
    patched = banks.Bank(**{**bank.__dict__, "deeplink_template": "bank://pay?acc={account}&amt={amount}"})
    monkeypatch.setattr(
        "guardian.api.qr.bank_by_bin", lambda b: patched if b == "970436" else None
    )
    async with await _client(build_app()) as c:
        r = await c.post(
            "/api/qr/encode", json=_encode_body(None, purpose="SPLIT_BILL"), headers=_headers()
        )
        assert r.status_code == 200, r.text
        assert r.json()["deeplink"] == "bank://pay?acc=1012345678&amt=150000"


async def test_encode_self_check_failure_is_500(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("guardian.api.qr.encode_vietqr", lambda *a, **k: "000201BROKEN")
    async with await _client(build_app()) as c:
        r = await c.post(
            "/api/qr/encode", json=_encode_body(None, purpose="SPLIT_BILL"), headers=_headers()
        )
        assert r.status_code == 500
        assert r.json()["error"] == "ENCODER_SELF_CHECK_FAILED"
