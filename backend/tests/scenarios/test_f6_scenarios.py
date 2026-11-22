"""F6 scenario A07 (assistant spend questions) and the spend endpoint against the reference."""

from __future__ import annotations

import uuid

import httpx
import pytest

from eval.matcher import REFERENCE_FUNCS
from eval.scenario_loader import Scenario, load_scenarios
from guardian.main import create_app
from tests.scenarios.runner import make_settings, run_scenario

SCENARIOS: dict[str, Scenario] = {s.id: s for s in load_scenarios() if s.id == "A07"}
HEADERS = {"X-Guardian-Session": str(uuid.uuid4())}


def test_a07_fixture_present() -> None:
    assert list(SCENARIOS) == ["A07"]
    assert len(SCENARIOS["A07"].cases) == 2


async def test_a07_scenario() -> None:
    result = await run_scenario(SCENARIOS["A07"])
    problems = [(c.endpoint, c.status_code, c.mismatches) for c in result.cases if not c.passed]
    assert not problems, problems


async def test_a07_answers_are_template_text() -> None:
    result = await run_scenario(SCENARIOS["A07"])
    cafe, grab = (c.response["result"] for c in result.cases)
    assert cafe["answer_vi"] == "Tháng này bạn đã chi 1.250.000 đ cho Cà phê (28 giao dịch)."
    assert grab["answer_vi"] == f"Tuần trước bạn có {grab['value']} lần chi cho Di chuyển."


def test_reference_rejects_wrong_value() -> None:
    ref = REFERENCE_FUNCS["spend_reference"]
    args = {"category": "CAFE", "period": "THIS_MONTH", "metric": "TOTAL"}
    assert ref(1_250_000, args, {})
    assert not ref(1_250_001, args, {})
    assert not ref(0, {**args, "period": "NEVER"}, {})


@pytest.mark.parametrize("category", ["ALL", "CAFE", "FOOD", "TRANSPORT", "TRANSFER_OUT"])
@pytest.mark.parametrize(
    "period",
    [
        "TODAY",
        "YESTERDAY",
        "THIS_WEEK",
        "LAST_WEEK",
        "THIS_MONTH",
        "LAST_MONTH",
        "LAST_7_DAYS",
        "LAST_30_DAYS",
        "LAST_3_MONTHS",
    ],
)
@pytest.mark.parametrize("metric", ["TOTAL", "COUNT", "AVERAGE_PER_TXN", "MAX_TXN"])
async def test_spend_endpoint_matches_reference(category: str, period: str, metric: str) -> None:
    app = create_app(make_settings())
    body = {"category": category, "period": period, "metric": metric}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/spend/query", json=body, headers=HEADERS)
    assert resp.status_code == 200
    data = resp.json()
    assert REFERENCE_FUNCS["spend_reference"](data["value"], body, data)
    assert data["unit"] == ("COUNT" if metric == "COUNT" else "VND")
    assert data["bucket_unit"] == ("WEEK" if period == "LAST_3_MONTHS" else "DAY")


async def test_spend_compare_previous_and_session_required() -> None:
    app = create_app(make_settings())
    body = {"category": "CAFE", "period": "LAST_7_DAYS", "metric": "COMPARE_PREVIOUS"}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        data = (await client.post("/api/spend/query", json=body, headers=HEADERS)).json()
        assert "from" in data["range"] and "to" in data["range"]
        assert data["previous_value"] is not None
        if data["previous_value"]:
            assert data["delta_percent"] == round((data["value"] - data["previous_value"]) * 100 / data["previous_value"])
        no_session = await client.post("/api/spend/query", json=body)
        assert no_session.status_code == 400
