"""Eval_Harness CLI: ``python -m eval.run_suite --runs 5 --k 3`` (run from ``backend/``)."""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from eval.report import (
    ScenarioStats,
    group_scores,
    pass_at_k,
    render_report,
    write_report,
)
from eval.runner import RunResult, run_scenario
from eval.scenario_loader import REPO_ROOT, Scenario, load_scenarios
from guardian.config import Settings, get_settings

DEFAULT_REPORT = REPO_ROOT / "eval_report.md"


def collect_latencies(result: RunResult, flow_a: list[float], flow_b_stage2: list[float]) -> None:
    for case in result.cases:
        body = case.response if isinstance(case.response, dict) else {}
        if "/api/flow-a/check" in case.endpoint:
            value = body.get("latency_ms")
            if isinstance(value, (int, float)):
                flow_a.append(float(value))
        elif "/api/flow-b/check" in case.endpoint:
            timings = body.get("stage_timings_ms")
            value = timings.get("stage2") if isinstance(timings, dict) else None
            if isinstance(value, (int, float)):
                flow_b_stage2.append(float(value))


def describe_failures(result: RunResult) -> list[str]:
    return [f"{c.endpoint}: {m}" for c in result.cases for m in c.mismatches]


async def run_all(
    scenarios: list[Scenario], runs: int, base: Settings
) -> tuple[list[ScenarioStats], list[float], list[float]]:
    stats: list[ScenarioStats] = []
    flow_a: list[float] = []
    flow_b: list[float] = []
    for scenario in scenarios:
        settings = base.model_copy(update={"guardian_debug": scenario.requires_debug})
        entry = ScenarioStats(scenario.id, scenario.group, runs, 0)
        for _ in range(runs):
            result = await run_scenario(scenario, settings)
            collect_latencies(result, flow_a, flow_b)
            if result.passed:
                entry.passes += 1
            elif not entry.failures:
                entry.failures = describe_failures(result)
        stats.append(entry)
    return stats, flow_a, flow_b


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="MoMo Guardian eval harness")
    parser.add_argument("--runs", type=int, default=5, help="runs per scenario (n)")
    parser.add_argument("--k", type=int, default=3, help="k in pass^k")
    parser.add_argument("--out", type=Path, default=DEFAULT_REPORT, help="report path")
    args = parser.parse_args(argv)
    if args.k < 1 or args.runs < args.k:
        parser.error("require 1 <= k <= runs")

    base = get_settings()
    scenarios = load_scenarios()
    stats, flow_a, flow_b = asyncio.run(run_all(scenarios, args.runs, base))
    report = render_report(
        stats,
        runs=args.runs,
        k=args.k,
        provider=base.llm_provider,
        flow_a_latencies_ms=flow_a,
        flow_b_stage2_ms=flow_b,
    )
    write_report(args.out, report)

    overall = pass_at_k(stats, args.k)
    print(f"provider={base.llm_provider} scenarios={len(stats)} runs={args.runs} k={args.k}")
    print(f"pass^{args.k} overall: {overall * 100:.1f}%" if overall is not None else "no scenarios")
    for group, score in group_scores(stats, args.k).items():
        if score is not None:
            print(f"  {group}: {score * 100:.1f}%")
    print(f"report: {args.out}")
    return 0 if overall == 1.0 else 1


if __name__ == "__main__":
    sys.exit(main())
