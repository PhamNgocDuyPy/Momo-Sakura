"""Flow A scenario fixtures (T13-T16, T22, T23, T25, T27, T28, T31) run through the API."""

from __future__ import annotations

import json
import uuid

import httpx
import pytest

from eval.scenario_loader import Scenario, load_scenarios
from guardian.main import create_app
from tests.scenarios.runner import make_settings, run_scenario

FLOW_A_IDS = ["T13", "T14", "T15", "T16", "T22", "T23", "T25", "T27", "T28", "T31"]
SCENARIOS: dict[str, Scenario] = {s.id: s for s in load_scenarios() if s.id in FLOW_A_IDS}


def test_all_flow_a_fixtures_present() -> None:
    assert sorted(SCENARIOS) == sorted(FLOW_A_IDS)


@pytest.mark.parametrize("scenario_id", FLOW_A_IDS)
async def test_flow_a_scenario(scenario_id: str) -> None:
    result = await run_scenario(SCENARIOS[scenario_id])
    problems = [(c.endpoint, c.status_code, c.mismatches) for c in result.cases if not c.passed]
    assert not problems, problems


async def test_t25_latency_under_200ms() -> None:
    result = await run_scenario(SCENARIOS["T25"])
    assert result.passed
    assert result.cases[0].response["latency_ms"] < 200


async def test_fast_unblock_audit_record(tmp_path) -> None:  # type: ignore[no-untyped-def]
    audit_path = tmp_path / "audit.jsonl"
    settings = make_settings(audit_log_path=str(audit_path))
    headers = {"X-Guardian-Session": str(uuid.uuid4())}
    transport = httpx.ASGITransport(app=create_app(settings))
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        first = (
            await client.post(
                "/api/flow-a/check",
                json={"bank_bin": "970407", "account_number": "19033344455501", "amount_vnd": 500000},
                headers=headers,
            )
        ).json()
        r = await client.post(
            "/api/flow-a/fast-unblock",
            json={
                "verdict_id": first["verdict_id"],
                "identity_check": {"method": "SANDBOX_OTP", "code": "123456"},
                "purpose": "PAY_RENT",
            },
            headers=headers,
        )
        assert r.status_code == 200, r.text
    records = [json.loads(line) for line in audit_path.read_text(encoding="utf-8").splitlines()]
    unblock = [x for x in records if x["channel"] == "FAST_UNBLOCK"]
    assert len(unblock) == 1
    extra = unblock[0]["extra"]
    assert "RC_SIMO_OR_MULE_HIGH_RISK" in extra["original_reason_codes"]
    assert extra["purpose"] == "PAY_RENT"
    assert extra["unblocked_at"]
