"""Run scenario fixtures through the FastAPI app (httpx.ASGITransport).

Shared by ``eval.run_suite``, ``guardian.api.eval`` and the pytest scenario tests.

Each run uses a fresh session id and a fresh app, so Risk_Memory never leaks.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

import httpx

from eval.matcher import match
from eval.scenario_loader import Scenario, resolve_prev
from guardian.config import Settings


@dataclass
class CaseResult:
    endpoint: str
    status_code: int
    response: Any
    mismatches: list[str]

    @property
    def passed(self) -> bool:
        return not self.mismatches


@dataclass
class RunResult:
    scenario_id: str
    cases: list[CaseResult] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all(c.passed for c in self.cases)


def make_settings(*, debug: bool = False, **overrides: object) -> Settings:
    base: dict[str, object] = {"llm_provider": "mock", "guardian_debug": debug}
    base.update(overrides)
    return Settings(_env_file=None, **base)  # type: ignore[arg-type]


async def run_scenario(scenario: Scenario, settings: Settings | None = None) -> RunResult:
    """Run all cases of a scenario in order with a new session."""
    from guardian.main import create_app  # lazy: guardian.main imports guardian.api.eval

    settings = settings or make_settings(debug=scenario.requires_debug)
    session_id = str(uuid.uuid4())
    result = RunResult(scenario_id=scenario.id)
    transport = httpx.ASGITransport(app=create_app(settings))
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        prev: Any = None
        for case in scenario.cases:
            method, _, path = case.endpoint.partition(" ")
            request = resolve_prev(case.request, prev) if prev is not None else case.request
            headers = {"X-Guardian-Session": session_id, **case.headers}
            if method.upper() == "GET":
                resp = await client.get(path, params=request, headers=headers)
            else:
                resp = await client.request(method.upper(), path, json=request, headers=headers)
            try:
                body: Any = resp.json()
            except ValueError:
                body = {}
            expect = dict(case.expect)
            mismatches = match(body, expect) if isinstance(body, dict) else ["non-JSON response"]
            if resp.status_code >= 400 and "http_status" not in expect:
                mismatches.append(f"unexpected HTTP status {resp.status_code}")
            result.cases.append(CaseResult(case.endpoint, resp.status_code, body, mismatches))
            prev = body
    return result
