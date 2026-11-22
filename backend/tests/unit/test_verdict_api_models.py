"""Unit tests for GuardianVerdict and the API envelope models."""

from __future__ import annotations

import json

import pytest
from hypothesis import given
from pydantic import ValidationError

from guardian.schemas.api_models import (
    CheckResponse,
    DebugOverrides,
    FlowACheckRequest,
    FlowBCheckRequest,
    Signals,
    UiHints,
)
from guardian.schemas.enums import DecisionTier
from guardian.schemas.verdict import GuardianVerdict
from tests.property.strategies.signals import api_signals


def _verdict(**over: object) -> dict[str, object]:
    base: dict[str, object] = {
        "decision_tier": "SOFT_FRICTION",
        "reason_codes": ["RC_COLD_START_NEEDS_CONTEXT"],
    }
    base.update(over)
    return base


def test_verdict_serializes_tier_by_name_and_round_trips() -> None:
    v = GuardianVerdict.model_validate(_verdict())
    assert v.decision_tier is DecisionTier.SOFT_FRICTION
    assert json.loads(v.model_dump_json())["decision_tier"] == "SOFT_FRICTION"
    assert GuardianVerdict.model_validate_json(v.model_dump_json()) == v


@pytest.mark.parametrize(
    "over",
    [
        {"reason_codes": ["RC_NOT_IN_REGISTRY"]},
        {"reason_codes": ["bad"]},
        {"reason_codes": []},
        {"reason_codes": ["RC_NO_SCAM_SIGNAL_FOUND"] * 7},
        {"cooling_off_seconds": 20},
        {"evidence_bullets": ["x"] * 5},
        {"system2_check_questions": ["q"] * 3},
        {"unknown_key": 1},
        {"decision_tier": "NOPE"},
    ],
)
def test_verdict_rejects_invalid(over: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        GuardianVerdict.model_validate(_verdict(**over))


def test_check_response_round_trip_and_forbids_extra() -> None:
    resp = CheckResponse(
        request_id="req_1",
        verdict_id="vd_1",
        channel="FLOW_A",
        verdict=GuardianVerdict.model_validate(_verdict()),
        ui_hints=UiHints(show_context_elicitation=True),
        latency_ms=4,
    )
    again = CheckResponse.model_validate_json(resp.model_dump_json())
    assert again == resp
    with pytest.raises(ValidationError):
        CheckResponse.model_validate({**resp.model_dump(mode="json"), "extra": 1})


def test_requests_forbid_extra_and_validate_fields() -> None:
    ok = {"bank_bin": "970436", "account_number": "1012345678", "amount_vnd": 150000}
    assert FlowACheckRequest.model_validate(ok).source_integrity == "USER_TYPED"
    for bad in ({**ok, "x": 1}, {**ok, "bank_bin": "12"}, {**ok, "amount_vnd": 0}):
        with pytest.raises(ValidationError):
            FlowACheckRequest.model_validate(bad)
    with pytest.raises(ValidationError):
        FlowBCheckRequest.model_validate({"content": {"origin": "PASTE", "text": "x"}, "debug": {"nope": 1}})


def test_debug_overrides_fields() -> None:
    d = DebugOverrides(simulate_llm_delay_ms=5000, simulate_skip_qr_verify=True)
    assert d.force_llm_output is None and d.simulate_redactor_failure is False


@given(api_signals())
def test_api_signals_strategy_yields_valid_models(sig: Signals) -> None:
    assert Signals.model_validate_json(sig.model_dump_json()) == sig
