"""Fixture coverage: T01-T31 / A01-A14 present, F1-F7 covered, Appendix A parity, gen_qr determinism."""
from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path
from typing import Any

import pytest

from eval.scenario_loader import FIXTURES_DIR, QR_SAMPLES_PATH, REPO_ROOT, Scenario, load_scenarios

SPEC_DIR = REPO_ROOT / ".kiro" / "specs" / "momo-guardian-web"
T_IDS = [f"T{n:02d}" for n in range(1, 32)]
A_IDS = [f"A{n:02d}" for n in range(1, 15)]
# Appendix A prose checks that a fixture expresses through a different field.
TOKEN_ALIASES: dict[tuple[str, str], tuple[str, ...]] = {
    ("T17", "requires_user_account_confirm"): ("RC_OCR_ACCOUNT_NEEDS_CONFIRM", "ABORT_WAIT_NAPAS_NAME_USER_CONFIRM"),
    ("T21", "requires_user_account_confirm"): ("RC_ACCOUNT_SWAP_REQUEST", "prefill.account_number"),
}
TIER_ORDER = {"ALLOW": 0, "SOFT_FRICTION": 1, "HARD_HOLD": 2}

SCENARIOS: dict[str, Scenario] = {s.id: s for s in load_scenarios()}
RAW: dict[str, dict[str, Any]] = {
    p.stem: json.loads(p.read_text(encoding="utf-8"))
    for p in (FIXTURES_DIR / "scenarios").glob("*.json")
    if not p.name.startswith("_")
}


def _appendix_a() -> dict[str, tuple[str, list[str]]]:
    text = (SPEC_DIR / "requirements.md").read_text(encoding="utf-8")
    section = text.split("## Phụ lục A", 1)[1]
    rows: dict[str, tuple[str, list[str]]] = {}
    for line in section.splitlines():
        m = re.match(r"^\|\s*(T\d{2})\s*\|(.*)$", line)
        if not m:
            continue
        cells = [c.strip() for c in m.group(2).split("|")]
        # cells: scenario title, tier, checks, ""
        rows[m.group(1)] = (cells[1], re.findall(r"`([^`]+)`", cells[2]))
    return rows


def _expect_blocks(scenario_id: str) -> list[dict[str, Any]]:
    return [c["expect"] for c in RAW[scenario_id]["cases"]]


def _expected_tiers(expect: dict[str, Any]) -> tuple[str | None, str | None]:
    """(exact tier, minimum tier) from a fixture expect block."""
    want = expect.get("decision_tier")
    if isinstance(want, dict):
        return None, want.get("min")
    return want, None


def test_all_scenarios_present() -> None:
    assert sorted(i for i in SCENARIOS if i.startswith("T")) == T_IDS
    assert sorted(i for i in SCENARIOS if i.startswith("A")) == A_IDS
    assert len(SCENARIOS) == len(T_IDS) + len(A_IDS)


@pytest.mark.parametrize("scenario_id", T_IDS + A_IDS)
def test_fixture_is_well_formed(scenario_id: str) -> None:
    raw = RAW[scenario_id]
    assert raw["id"] == scenario_id
    assert raw["title_vi"] and raw["description_vi"]
    assert raw["channel"] and raw["group"]
    assert raw["cases"]
    assert all(c.get("endpoint") and c.get("expect") for c in raw["cases"])


def _feature_of(scenario_id: str, design_rows: dict[str, str]) -> str | None:
    m = re.match(r"^F([1-7])\b", RAW[scenario_id]["description_vi"])
    if m:
        return f"F{m.group(1)}"
    m = re.match(r"^F([1-7])\b", design_rows.get(scenario_id, ""))
    return f"F{m.group(1)}" if m else None


def test_assistant_scenarios_cover_f1_to_f7() -> None:
    design = (SPEC_DIR / "design.md").read_text(encoding="utf-8")
    rows = {
        m.group(1): m.group(2).strip()
        for m in re.finditer(r"^\|\s*(A\d{2})\s*\|\s*([^|]+)\|", design, re.MULTILINE)
    }
    covered = {_feature_of(i, rows) for i in A_IDS}
    assert {f"F{n}" for n in range(1, 8)} <= covered


@pytest.mark.parametrize("scenario_id", T_IDS)
def test_expected_tier_and_codes_match_appendix_a(scenario_id: str) -> None:
    tier_cell, tokens = _appendix_a()[scenario_id]
    expects = _expect_blocks(scenario_id)
    mentioned = [t for t in TIER_ORDER if t in tier_cell]
    states = [_expected_tiers(e) for e in expects]

    if tier_cell.startswith("≥"):
        floor = TIER_ORDER[mentioned[0]]
        for exact, minimum in states:
            level = TIER_ORDER[exact] if exact else TIER_ORDER[minimum] if minimum else None
            assert level is None or level >= floor, (exact, minimum)
        assert any(exact or minimum for exact, minimum in states)
    elif mentioned:
        for exact, minimum in states:
            if exact:
                assert exact in mentioned, (exact, tier_cell)
            if minimum:
                assert TIER_ORDER[minimum] <= max(TIER_ORDER[t] for t in mentioned)
        assert {e for e, _ in states if e} <= set(mentioned)
        assert any(e or m for e, m in states)

    blob = json.dumps(expects, ensure_ascii=False)
    for token in tokens:
        alternatives = TOKEN_ALIASES.get((scenario_id, token), (token,))
        assert any(a in blob for a in alternatives), f"{scenario_id}: Appendix A token {token!r} not asserted by fixture"


def test_appendix_a_lists_all_t_scenarios() -> None:
    assert sorted(_appendix_a()) == T_IDS


def test_gen_qr_regenerates_qr_samples_identically(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    spec = importlib.util.spec_from_file_location("gen_qr_under_test", FIXTURES_DIR / "gen_qr.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    committed = QR_SAMPLES_PATH.read_bytes()
    regenerated = (json.dumps(module.build(), ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    assert regenerated == committed
