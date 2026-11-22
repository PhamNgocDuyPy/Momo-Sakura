from __future__ import annotations

from pathlib import Path

import pytest

from eval.matcher import match
from eval.scenario_loader import ScenarioError, load_scenarios, parse_scenario, resolve_prev

RESP = {
    "verdict": {"decision_tier": "HARD_HOLD", "reason_codes": ["RC_A", "RC_B"]},
    "qr": {"result": "BAD_CRC", "flags": ["X"]},
    "stop_codes": ["S1"],
    "trace": [{"kind": "tool", "name": "verify_vietqr_emvco"}],
    "latency_ms": 50,
    "prefill": {"amount_vnd": 200000},
}


def test_match_passes() -> None:
    expect = {
        "decision_tier": {"min": "SOFT_FRICTION"},
        "reason_codes_include": ["RC_A"],
        "reason_codes_exclude": ["RC_Z"],
        "qr_result": "BAD_CRC",
        "qr_flags_include": ["X"],
        "stop_codes_include": ["S1"],
        "trace_tools_subset_of_allowlist": True,
        "assert": [
            {"path": "latency_ms", "op": "lt", "value": 200},
            {"path": "prefill.amount_vnd", "op": "eq", "value": 200000},
            {"path": "extensions", "op": "absent"},
        ],
    }
    assert match(RESP, expect) == []


def test_match_reports_mismatches() -> None:
    expect = {
        "decision_tier": "ALLOW",
        "reason_codes_exclude": ["RC_A"],
        "trace_tools_subset_of_allowlist": True,
        "assert": [{"path": "latency_ms", "op": "gt", "value": 100}],
    }
    assert len(match(RESP, expect)) == 3
    bad_trace = {**RESP, "trace": [{"kind": "tool", "name": "evil"}]}
    assert match(bad_trace, {"trace_tools_subset_of_allowlist": True})


def test_placeholders(tmp_path: Path) -> None:
    sc = parse_scenario(
        {
            "id": "X",
            "cases": [{"endpoint": "POST /p", "request": {"qr_payload": "{{qr:T13}}"}, "expect": {}}],
        },
        {"T13": "PAYLOAD"},
    )
    assert sc.cases[0].request["qr_payload"] == "PAYLOAD"
    assert resolve_prev({"p": "{{prev.prefill}}", "s": "a{{prev.latency_ms}}"}, RESP) == {
        "p": {"amount_vnd": 200000},
        "s": "a50",
    }
    with pytest.raises(ScenarioError):
        resolve_prev("{{prev.nope}}", RESP)


def test_loader_skips_underscore_files(tmp_path: Path) -> None:
    (tmp_path / "_matcher_vectors.json").write_text("[]", encoding="utf-8")
    (tmp_path / "T1.json").write_text(
        '{"id":"T1","requires_debug":true,"cases":[]}', encoding="utf-8"
    )
    loaded = load_scenarios(tmp_path)
    assert [s.id for s in loaded] == ["T1"] and loaded[0].requires_debug
