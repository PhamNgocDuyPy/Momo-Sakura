"""Eval endpoints for the Demo_Page and the Eval_Harness."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from eval.runner import run_scenario
from eval.scenario_loader import Scenario, ScenarioError, load_scenario, load_scenarios
from guardian.api.deps import GuardianError, get_container
from guardian.container import Container
from guardian.policy.templates_vi import ERRORS

router = APIRouter(prefix="/api/eval", tags=["eval"])

MAX_RUNS = 20


class EvalRunRequest(BaseModel):
    scenario_id: str = Field(min_length=1, max_length=16)
    runs: int = Field(default=1, ge=1, le=MAX_RUNS)


def _strip_debug(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _strip_debug(v) for k, v in value.items() if k != "debug"}
    if isinstance(value, list):
        return [_strip_debug(v) for v in value]
    return value


def _serialize(scenario: Scenario, debug_enabled: bool) -> dict[str, Any]:
    cases = []
    for case in scenario.cases:
        request = case.request if debug_enabled else _strip_debug(case.request)
        cases.append(
            {
                "endpoint": case.endpoint,
                "request": request,
                "expect": case.expect,
                "headers": case.headers,
            }
        )
    return {
        "id": scenario.id,
        "title_vi": scenario.title_vi,
        "description_vi": scenario.description_vi,
        "group": scenario.group,
        "channel": scenario.channel,
        "requires_debug": scenario.requires_debug,
        "cases": cases,
    }


@router.get("/scenarios")
async def list_scenarios(container: Container = Depends(get_container)) -> list[dict[str, Any]]:
    debug_enabled = container.settings.guardian_debug
    return [_serialize(s, debug_enabled) for s in load_scenarios()]


@router.post("/run")
async def run_eval(
    body: EvalRunRequest, container: Container = Depends(get_container)
) -> dict[str, Any]:
    try:
        scenario = load_scenario(body.scenario_id)
    except ScenarioError as exc:
        raise GuardianError(404, "NOT_FOUND", "") from exc
    if scenario.requires_debug and not container.settings.guardian_debug:
        raise GuardianError(403, "DEBUG_DISABLED", ERRORS["DEBUG_DISABLED"])
    settings = container.settings.model_copy(
        update={"guardian_debug": scenario.requires_debug or container.settings.guardian_debug}
    )
    runs: list[dict[str, Any]] = []
    for _ in range(body.runs):
        result = await run_scenario(scenario, settings)
        last = result.cases[-1].response if result.cases else {}
        last = last if isinstance(last, dict) else {}
        verdict = last.get("verdict") if isinstance(last.get("verdict"), dict) else last
        runs.append(
            {
                "passed": result.passed,
                "actual": {
                    "decision_tier": verdict.get("decision_tier"),
                    "reason_codes": verdict.get("reason_codes", []),
                    "stop_codes": last.get("stop_codes", []),
                },
                "mismatches": [m for c in result.cases for m in c.mismatches],
            }
        )
    return {
        "scenario_id": scenario.id,
        "passed": all(r["passed"] for r in runs),
        "runs": runs,
    }
