"""Load scenario fixtures from ``fixtures/scenarios/*.json``.

Placeholders:
- ``{{qr:<ID>}}`` is resolved at load time from ``fixtures/qr_samples.json``.
- ``{{prev.<path>}}`` is resolved at run time from the previous case response
  (see :func:`resolve_prev`).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES_DIR = REPO_ROOT / "fixtures"
SCENARIOS_DIR = FIXTURES_DIR / "scenarios"
QR_SAMPLES_PATH = FIXTURES_DIR / "qr_samples.json"

_PLACEHOLDER = re.compile(r"\{\{\s*(qr|prev)\s*[:.]\s*([^{}]+?)\s*\}\}")
_FULL_PLACEHOLDER = re.compile(r"^\{\{\s*(qr|prev)\s*[:.]\s*([^{}]+?)\s*\}\}$")


class ScenarioError(Exception):
    """Raised for malformed scenario fixtures or unresolved placeholders."""


@dataclass(frozen=True)
class Case:
    endpoint: str
    request: dict[str, Any]
    expect: dict[str, Any]
    headers: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class Scenario:
    id: str
    title_vi: str
    description_vi: str
    group: str
    channel: str
    requires_debug: bool
    cases: tuple[Case, ...]


def load_qr_samples(path: Path = QR_SAMPLES_PATH) -> dict[str, str]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return {key: str(value["payload"]) for key, value in raw.items()}


def _walk(value: Any, fn: Any) -> Any:
    if isinstance(value, dict):
        return {k: _walk(v, fn) for k, v in value.items()}
    if isinstance(value, list):
        return [_walk(v, fn) for v in value]
    if isinstance(value, str):
        return fn(value)
    return value


def _substitute_qr(value: Any, qr: dict[str, str]) -> Any:
    def sub(text: str) -> str:
        def repl(m: re.Match[str]) -> str:
            if m.group(1) != "qr":
                return m.group(0)
            key = m.group(2)
            if key not in qr:
                raise ScenarioError(f"Unknown QR sample placeholder: {key}")
            return qr[key]

        return _PLACEHOLDER.sub(repl, text)

    return _walk(value, sub)


def get_path(data: Any, path: str) -> Any:
    """Resolve a dotted path (dict keys and integer list indexes). Raises KeyError."""
    current = data
    for part in path.split("."):
        if isinstance(current, dict):
            if part not in current:
                raise KeyError(path)
            current = current[part]
        elif isinstance(current, list):
            try:
                current = current[int(part)]
            except (ValueError, IndexError) as exc:
                raise KeyError(path) from exc
        else:
            raise KeyError(path)
    return current


def resolve_prev(value: Any, prev_response: Any) -> Any:
    """Replace ``{{prev.<path>}}``. A whole-string placeholder keeps the original type."""

    def sub(text: str) -> Any:
        full = _FULL_PLACEHOLDER.match(text)
        if full and full.group(1) == "prev":
            try:
                return get_path(prev_response, full.group(2))
            except KeyError as exc:
                raise ScenarioError(f"Unresolved placeholder: prev.{full.group(2)}") from exc

        def repl(m: re.Match[str]) -> str:
            if m.group(1) != "prev":
                return m.group(0)
            try:
                return str(get_path(prev_response, m.group(2)))
            except KeyError as exc:
                raise ScenarioError(f"Unresolved placeholder: prev.{m.group(2)}") from exc

        return _PLACEHOLDER.sub(repl, text)

    return _walk(value, sub)


def parse_scenario(raw: dict[str, Any], qr: dict[str, str]) -> Scenario:
    try:
        cases = tuple(
            Case(
                endpoint=str(c["endpoint"]),
                request=_substitute_qr(c.get("request", {}), qr),
                expect=c.get("expect", {}),
                headers=dict(c.get("headers", {})),
            )
            for c in raw["cases"]
        )
        return Scenario(
            id=str(raw["id"]),
            title_vi=str(raw.get("title_vi", "")),
            description_vi=str(raw.get("description_vi", "")),
            group=str(raw.get("group", "")),
            channel=str(raw.get("channel", "")),
            requires_debug=bool(raw.get("requires_debug", False)),
            cases=cases,
        )
    except KeyError as exc:
        raise ScenarioError(f"Scenario missing field {exc}") from exc


def load_scenarios(
    directory: Path = SCENARIOS_DIR, qr_path: Path = QR_SAMPLES_PATH
) -> list[Scenario]:
    """Load all scenarios sorted by id; files starting with ``_`` are skipped."""
    if not directory.is_dir():
        return []
    qr = load_qr_samples(qr_path)
    scenarios = []
    for path in sorted(directory.glob("*.json")):
        if path.name.startswith("_"):
            continue
        raw = json.loads(path.read_text(encoding="utf-8"))
        scenarios.append(parse_scenario(raw, qr))
    return scenarios


def load_scenario(scenario_id: str, directory: Path = SCENARIOS_DIR) -> Scenario:
    for scenario in load_scenarios(directory):
        if scenario.id == scenario_id:
            return scenario
    raise ScenarioError(f"Unknown scenario: {scenario_id}")
