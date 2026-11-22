"""Unit tests for Floor/FloorSet, TraceRecorder and RequestContext."""

from __future__ import annotations

import uuid

import pytest
from hypothesis import given

from guardian.control_plane.session import RequestContext, payer_session_hash
from guardian.policy import floors as floors_module
from guardian.policy.floors import Floor, FloorSet
from guardian.reason_codes import (
    RC_COLD_START_NEEDS_CONTEXT,
    RC_FAN_IN_VELOCITY_HIGH,
    RC_SIMO_OR_MULE_HIGH_RISK,
)
from guardian.schemas import enums
from guardian.schemas.enums import DecisionTier, HardSource
from guardian.schemas.trace import TraceRecorder
from tests.property.strategies.signals import floors as floor_strategy
from tests.property.strategies.signals import floorsets

H = DecisionTier.HARD_HOLD
S = DecisionTier.SOFT_FRICTION


def test_hard_source_is_reexported() -> None:
    assert floors_module.HardSource is enums.HardSource


def test_hard_floor_requires_hard_source() -> None:
    with pytest.raises(ValueError):
        Floor(H, RC_SIMO_OR_MULE_HIGH_RISK, "R4")


def test_unknown_reason_code_rejected() -> None:
    with pytest.raises(ValueError):
        Floor(S, "RC_DOES_NOT_EXIST", "R4")


def test_empty_floorset_defaults() -> None:
    fs = FloorSet()
    assert fs.final_tier == DecisionTier.ALLOW
    assert fs.cooling_off_seconds() == 0
    assert not fs.allow_fast_unblock()


def test_fast_unblock_only_for_gnn_or_velocity() -> None:
    gnn = Floor(H, RC_SIMO_OR_MULE_HIGH_RISK, "R4", HardSource.GNN_MULE, frozenset({"FAST_UNBLOCK"}))
    vel = Floor(H, RC_FAN_IN_VELOCITY_HIGH, "R4", HardSource.FAN_IN_VELOCITY, frozenset({"FAST_UNBLOCK"}))
    simo = Floor(H, RC_SIMO_OR_MULE_HIGH_RISK, "R4", HardSource.SIMO_HIT)
    assert FloorSet([gnn, vel]).allow_fast_unblock()
    assert not FloorSet([gnn, simo]).allow_fast_unblock()


def test_remove_removable_lowers_tier_and_keeps_others() -> None:
    gnn = Floor(H, RC_SIMO_OR_MULE_HIGH_RISK, "R4", HardSource.GNN_MULE, frozenset({"FAST_UNBLOCK"}))
    cold = Floor(S, RC_COLD_START_NEEDS_CONTEXT, "COLD_START", None, frozenset({"CONTEXT_IN_STORE"}))
    fs = FloorSet([gnn, cold])
    assert fs.remove_removable("FAST_UNBLOCK") == [gnn]
    assert fs.final_tier == S
    assert fs.remove_removable("CONTEXT_IN_STORE") == [cold]
    assert fs.final_tier == DecisionTier.ALLOW


@given(floorsets(), floor_strategy())
def test_adding_floor_never_lowers_tier_or_cooling(fs: FloorSet, extra: Floor) -> None:
    tier, cooling = fs.final_tier, fs.cooling_off_seconds()
    fs.add(extra)
    assert fs.final_tier >= tier
    assert fs.cooling_off_seconds() >= cooling
    assert fs.cooling_off_seconds() in {0, 15, 30, 60, 300}


def test_trace_recorder_sequences_and_validates_detail() -> None:
    t = TraceRecorder()
    a = t.record("tool", "verify_vietqr_emvco", detail={"result": "VALID_VIETQR"})
    b = t.record("stage", "label_untrusted", "skipped")
    assert (a.seq, b.seq) == (1, 2)
    assert t.has("verify_vietqr_emvco", "ok")
    with pytest.raises(ValueError):
        t.record("tool", "x", detail={"bad": object()})


def test_payer_hash_and_context() -> None:
    sid = str(uuid.uuid4())
    h = payer_session_hash("secret", sid)
    assert len(h) == 32 and h == payer_session_hash("secret", sid)
    assert h != payer_session_hash("other", sid)
    ctx = RequestContext.create(sid, "FLOW_A", "secret")
    assert ctx.payer_session_hash == h and ctx.floors.final_tier == DecisionTier.ALLOW
    with pytest.raises(ValueError):
        RequestContext.create("not-a-uuid", "FLOW_A", "secret")
