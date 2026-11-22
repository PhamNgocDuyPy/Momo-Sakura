"""Quick regression: the Eval_Harness with ``--runs 1`` on MockLLM passes every scenario."""
from __future__ import annotations

from pathlib import Path

import pytest

from eval import run_suite
from eval.report import pass_at_k
from eval.scenario_loader import load_scenarios
from guardian.config import Settings


async def test_harness_runs_all_scenarios_once_on_mock() -> None:
    scenarios = load_scenarios()
    base = Settings(_env_file=None, llm_provider="mock")  # type: ignore[call-arg]
    stats, flow_a, flow_b = await run_suite.run_all(scenarios, 1, base)
    failing = {s.scenario_id: s.failures for s in stats if s.passes != s.runs}
    assert not failing, failing
    assert len(stats) == 45
    assert pass_at_k(stats, 1) == 1.0
    assert flow_a and flow_b


def test_cli_writes_report(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    monkeypatch.setattr(run_suite, "load_scenarios", lambda: load_scenarios()[:2])
    out = tmp_path / "eval_report.md"
    assert run_suite.main(["--runs", "1", "--k", "1", "--out", str(out)]) == 0
    text = out.read_text(encoding="utf-8")
    assert "`mock`" in text
    assert "pass^k với MockLLM chỉ chứng minh Control Plane chạy đúng" in text
