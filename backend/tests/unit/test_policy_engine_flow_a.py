"""Unit tests for PolicyEngine Flow A rules (task 7.1)."""
from __future__ import annotations

import uuid

import pytest

from guardian.control_plane.session import RequestContext
from guardian.control_plane.tool_runner import Abort, Allow, ToolNotAllowed
from guardian.policy.engine import UNCONFIRMED_ACCOUNT_ABORTED, PolicyEngine
from guardian.providers.base import PayerHistory, RecipientRisk
from guardian.reason_codes import (
    RC_CIRCULAR50_STRUCTURING_RISK,
    RC_COLD_START_NEEDS_CONTEXT,
    RC_FAN_IN_VELOCITY_HIGH,
    RC_FLOWB_FLAGGED_RECENTLY,
    RC_GREY_ZONE_RECIPIENT,
    RC_OCR_ACCOUNT_NEEDS_CONFIRM,
    RC_QR_CHECK_BYPASS_DETECTED,
    RC_SIMO_OR_MULE_HIGH_RISK,
    RC_TRUSTED_PAYEE_HISTORY,
    RC_VIETQR_TAMPERED_BAD_CRC,
)
from guardian.schemas.enums import DecisionTier, QrResult, SourceIntegrity, StopCode
from guardian.stores.risk_memory import RiskMemoryEntry
from guardian.tools.vietqr import QrVerification
from datetime import datetime, timezone

engine = PolicyEngine(fan_in_velocity_threshold=10)


def make_ctx(**kw) -> RequestContext:
    return RequestContext.create(str(uuid.uuid4()), "FLOW_A", "secret", **kw)


def codes(ctx: RequestContext) -> set[str]:
    return {f.reason_code for f in ctx.floors}


def test_r2_aborts_unconfirmed_ocr() -> None:
    ctx = make_ctx(source_integrity=SourceIntegrity.OCR_UNCONFIRMED)
    decision = engine.before_call("lookup_recipient_risk_and_simo", {}, ctx)
    assert isinstance(decision, Abort)
    assert decision.result_code == UNCONFIRMED_ACCOUNT_ABORTED
    assert decision.stop_code == StopCode.ABORT_WAIT_NAPAS_NAME_USER_CONFIRM
    assert codes(ctx) == {RC_OCR_ACCOUNT_NEEDS_CONFIRM}


def test_confirmed_source_allowed_and_unknown_tool_denied() -> None:
    ctx = make_ctx(source_integrity=SourceIntegrity.USER_TYPED)
    assert isinstance(engine.before_call("lookup_recipient_risk_and_simo", {}, ctx), Allow)
    with pytest.raises(ToolNotAllowed):
        engine.before_call("rm_rf", {}, ctx)


def test_after_call_qr_and_r4_and_memory() -> None:
    ctx = make_ctx()
    engine.after_call("verify_vietqr_emvco", QrVerification(result=QrResult.BAD_CRC), ctx)
    engine.after_call(
        "lookup_recipient_risk_and_simo",
        RecipientRisk(simo_hit=True, gnn_mule_score=0.9, fan_in_senders_per_hour=12),
        ctx,
    )
    now = datetime.now(timezone.utc)
    engine.after_call("risk_memory_lookup", RiskMemoryEntry("k", "RC_X", now, now), ctx)
    assert {
        RC_VIETQR_TAMPERED_BAD_CRC,
        RC_SIMO_OR_MULE_HIGH_RISK,
        RC_FAN_IN_VELOCITY_HIGH,
        RC_FLOWB_FLAGGED_RECENTLY,
    } <= codes(ctx)
    assert ctx.floors.final_tier == DecisionTier.HARD_HOLD
    assert not ctx.floors.allow_fast_unblock()


def test_gnn_only_is_fast_unblockable_and_threshold_boundary() -> None:
    ctx = make_ctx()
    engine.after_call("lookup_recipient_risk_and_simo", RecipientRisk(gnn_mule_score=0.85), ctx)
    assert ctx.floors.allow_fast_unblock()
    ctx2 = make_ctx()
    engine.after_call("lookup_recipient_risk_and_simo", RecipientRisk(gnn_mule_score=0.84), ctx2)
    assert ctx2.floors.final_tier == DecisionTier.ALLOW


def test_before_emit_r6_r5_grey_baseline() -> None:
    ctx = make_ctx(qr_present=True)
    engine.before_emit(
        ctx,
        amount_vnd=9_000_000,
        total_24h_vnd=11_000_000,
        risk=RecipientRisk(account_age_days=10),
        history=PayerHistory(has_history=True),
    )
    assert {
        RC_QR_CHECK_BYPASS_DETECTED,
        RC_CIRCULAR50_STRUCTURING_RISK,
        RC_GREY_ZONE_RECIPIENT,
        RC_TRUSTED_PAYEE_HISTORY,
    } <= codes(ctx)
    assert StopCode.TEMPORAL_BYPASS_DETECTED_MISSING_VIETQR_CHECK in ctx.stop_codes


def test_r5_boundaries() -> None:
    for amount, total, expected in [
        (9_000_000, 11_000_000, True),
        (9_000_000, 10_999_999, False),
        (10_000_000, 20_000_000, False),
        (8_999_999, 20_000_000, False),
    ]:
        ctx = make_ctx()
        engine.before_emit(ctx, amount_vnd=amount, total_24h_vnd=total)
        assert (RC_CIRCULAR50_STRUCTURING_RISK in codes(ctx)) is expected


def test_cold_start_vs_trusted_baseline() -> None:
    cold = make_ctx()
    engine.before_emit(cold, amount_vnd=100_000, risk=RecipientRisk(), history=PayerHistory())
    assert codes(cold) == {RC_COLD_START_NEEDS_CONTEXT}
    trusted = make_ctx()
    engine.before_emit(
        trusted, amount_vnd=100_000, risk=RecipientRisk(), history=PayerHistory(has_history=True)
    )
    assert codes(trusted) == {RC_TRUSTED_PAYEE_HISTORY}
    assert trusted.floors.final_tier == DecisionTier.ALLOW


def test_grey_zone_suppressed_by_hard_signal() -> None:
    ctx = make_ctx()
    risk = RecipientRisk(simo_hit=True, account_age_days=1)
    engine.after_call("lookup_recipient_risk_and_simo", risk, ctx)
    engine.before_emit(ctx, amount_vnd=1_000, risk=risk, history=PayerHistory())
    assert RC_GREY_ZONE_RECIPIENT not in codes(ctx)
    assert RC_COLD_START_NEEDS_CONTEXT not in codes(ctx)


def test_before_persist_consent() -> None:
    no = make_ctx()
    assert engine.before_persist(no).hash_only
    assert not no.stop_codes
    asked = engine.before_persist(no, wants_evidence=True)
    assert asked.stop_code == StopCode.LAW_91_CONSENT_REQUIRED
    assert StopCode.LAW_91_CONSENT_REQUIRED in no.stop_codes
    yes = make_ctx(explicit_consent_flag=True)
    assert engine.before_persist(yes, wants_evidence=True).store_evidence
