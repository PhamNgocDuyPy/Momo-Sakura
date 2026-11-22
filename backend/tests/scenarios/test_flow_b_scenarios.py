"""Flow B scenario fixtures (T01-T12, T17-T21, T24, T26, T29, T30) run through the API."""

from __future__ import annotations

import uuid

import httpx
import pytest

from eval.scenario_loader import Scenario, load_scenarios
from guardian.main import create_app
from tests.scenarios.runner import make_settings, run_scenario

FLOW_B_IDS = [
    *(f"T{n:02d}" for n in range(1, 13)),
    "T17", "T18", "T19", "T20", "T21", "T24", "T26", "T29", "T30",
]  # fmt: skip
SCENARIOS: dict[str, Scenario] = {s.id: s for s in load_scenarios() if s.id in FLOW_B_IDS}
FLOW_B_URL = "/api/flow-b/check?stream=false"
SIMO_ACCOUNT = {"bank_bin": "970407", "account_number": "1903777888999"}


def test_all_flow_b_fixtures_present() -> None:
    assert sorted(SCENARIOS) == sorted(FLOW_B_IDS)


@pytest.mark.parametrize("scenario_id", FLOW_B_IDS)
async def test_flow_b_scenario(scenario_id: str) -> None:
    result = await run_scenario(SCENARIOS[scenario_id])
    problems = [(c.endpoint, c.status_code, c.mismatches) for c in result.cases if not c.passed]
    assert not problems, problems


async def test_t17_skips_recipient_lookup_before_confirmation() -> None:
    result = await run_scenario(SCENARIOS["T17"])
    body = result.cases[0].response
    names = [s["name"] for s in body["trace"]]
    assert "lookup_recipient_risk_and_simo" not in names
    assert body["name_confirmation"] is not None


async def test_t26_redacted_counts_and_no_egress_block() -> None:
    result = await run_scenario(SCENARIOS["T26"])
    body = result.cases[0].response
    step = next(s for s in body["trace"] if s["name"] == "redact_pii_local")
    assert step["detail"]["redacted"] == {"CCCD": 1, "SDT": 1}
    assert "PII_EGRESS_BLOCKED" not in body["stop_codes"]


async def test_t29_stage_timings() -> None:
    result = await run_scenario(SCENARIOS["T29"])
    assert result.passed
    timings = result.cases[0].response["stage_timings_ms"]
    assert timings["stage2"] < 250
    assert timings["total"] < 4600


async def test_flow_b_hard_flags_recipient_for_flow_a_same_session_only() -> None:
    """Handoff: Flow B HARD for 1903777888999 TCB, then Flow A in the same session."""
    settings = make_settings()
    app = create_app(settings)
    session = {"X-Guardian-Session": str(uuid.uuid4())}
    other = {"X-Guardian-Session": str(uuid.uuid4())}
    flow_b = {
        "content": {
            "origin": "PASTE",
            "text": "Đây là Công an quận 1, tài khoản VNeID của bạn liên quan đường dây rửa tiền, "
            "chuyển 50tr vào stk 1903777888999 TCB để xác minh, không được nói với ai",
        }
    }
    flow_a = {**SIMO_ACCOUNT, "amount_vnd": 200_000, "source_integrity": "USER_TYPED"}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post(FLOW_B_URL, json=flow_b, headers=session)
        assert r.json()["verdict"]["decision_tier"] == "HARD_HOLD"
        same = (await client.post("/api/flow-a/check", json=flow_a, headers=session)).json()
        assert "RC_FLOWB_FLAGGED_RECENTLY" in same["verdict"]["reason_codes"]
        diff = (await client.post("/api/flow-a/check", json=flow_a, headers=other)).json()
        assert "RC_FLOWB_FLAGGED_RECENTLY" not in diff["verdict"]["reason_codes"]
