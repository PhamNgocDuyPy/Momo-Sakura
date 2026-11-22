"""F1 scenario fixtures A01-A02: paste a transfer message, prefill, then Flow A."""

from __future__ import annotations

import pytest

from eval.scenario_loader import Scenario, load_scenarios
from tests.scenarios.runner import run_scenario

F1_IDS = ["A01", "A02"]
SCENARIOS: dict[str, Scenario] = {s.id: s for s in load_scenarios() if s.id in F1_IDS}
SLANG_AMOUNTS = [500_000, 1_000_000, 1_500_000, 200_000, 1_500_000]


def test_f1_fixtures_present() -> None:
    assert sorted(SCENARIOS) == F1_IDS


@pytest.mark.parametrize("scenario_id", F1_IDS)
async def test_f1_scenario(scenario_id: str) -> None:
    result = await run_scenario(SCENARIOS[scenario_id])
    problems = [(c.endpoint, c.status_code, c.mismatches) for c in result.cases if not c.passed]
    assert not problems, problems


async def test_a01_flow_b_then_flow_a_uses_prefill() -> None:
    result = await run_scenario(SCENARIOS["A01"])
    flow_b, flow_a = result.cases
    prefill = flow_b.response["prefill"]
    assert (prefill["bank_bin"], prefill["account_number"], prefill["amount_vnd"], prefill["memo"]) == (
        "970436",
        "0123456789",
        200_000,
        "tiền cơm",
    )
    assert prefill["source_integrity_for_flow_a"] == "USER_TYPED"
    assert flow_a.response["channel"] == "FLOW_A"
    # Flow A never calls an LLM.
    assert all(step["kind"] != "llm" for step in flow_a.response["trace"])


async def test_a02_five_slang_amounts() -> None:
    result = await run_scenario(SCENARIOS["A02"])
    assert [c.response["prefill"]["amount_vnd"] for c in result.cases] == SLANG_AMOUNTS
    assert result.passed
