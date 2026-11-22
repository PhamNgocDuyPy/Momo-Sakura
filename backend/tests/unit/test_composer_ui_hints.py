from datetime import datetime, timedelta, timezone

import pytest

from guardian.policy.composer import compose_verdict, passes_honesty
from guardian.policy.floors import Floor, FloorSet
from guardian.policy.ui_hints import compute_ui_hints, is_late_night
from guardian.reason_codes import REGISTRY
from guardian.schemas.api_models import Prefill, TrustedContactRef
from guardian.schemas.enums import Cue, DecisionTier, HardSource
from guardian.policy.composer import ComposerInvalid


def _soft(code: str) -> Floor:
    return Floor(DecisionTier.SOFT_FRICTION, code, "CUE")


def test_orders_by_tier_then_priority_and_dedups() -> None:
    floors = FloorSet(
        [
            _soft("RC_GREY_ZONE_RECIPIENT"),
            Floor(DecisionTier.HARD_HOLD, "RC_SIMO_OR_MULE_HIGH_RISK", "R4", HardSource.SIMO_HIT),
            _soft("RC_GREY_ZONE_RECIPIENT"),
            _soft("RC_UPFRONT_FEE_REQUEST"),
        ]
    )
    out = compose_verdict(floors)
    assert out.verdict.reason_codes == [
        "RC_SIMO_OR_MULE_HIGH_RISK",
        "RC_UPFRONT_FEE_REQUEST",
        "RC_GREY_ZONE_RECIPIENT",
    ]
    assert out.verdict.decision_tier == DecisionTier.HARD_HOLD
    assert out.verdict.cooling_off_seconds == 60
    assert out.verdict.system2_check_questions  # grey zone questions


def test_caps_codes_bullets_and_overflow() -> None:
    soft_codes = [c for c, s in REGISTRY.items() if s.min_tier == DecisionTier.SOFT_FRICTION][:8]
    out = compose_verdict(FloorSet(_soft(c) for c in soft_codes))
    assert len(out.verdict.reason_codes) == 6
    assert len(out.overflow_reason_codes) == 2
    assert len(out.verdict.evidence_bullets) == 4


def test_questions_priority_and_cap() -> None:
    out = compose_verdict(
        FloorSet([_soft("RC_GREY_ZONE_RECIPIENT")]),
        context_playbook="IMPERSONATE_AUTHORITY_VNEID",
        extraction_playbook="DEEPFAKE_RELATIVE_EMERGENCY",
    )
    assert len(out.verdict.system2_check_questions) == 2
    assert "yêu cầu chuyển tiền" in out.verdict.system2_check_questions[0]


def test_ocr_sets_account_confirm_and_empty_floors_invalid() -> None:
    out = compose_verdict(FloorSet([_soft("RC_COLD_START_NEEDS_CONTEXT")]), origin_ocr=True)
    assert out.verdict.requires_user_account_confirm
    with pytest.raises(ComposerInvalid):
        compose_verdict(FloorSet())


def test_honesty_filter_nfc() -> None:
    assert not passes_honesty("Giao dịch 100% An Toàn")
    assert not passes_honesty("100% SAFE")
    assert passes_honesty("Guardian chưa thấy dấu hiệu lừa đảo")


def test_late_night_gmt7() -> None:
    utc = timezone.utc
    assert is_late_night(datetime(2026, 1, 1, 16, 30, tzinfo=utc))  # 23:30 GMT+7
    assert not is_late_night(datetime(2026, 1, 1, 22, 0, tzinfo=utc))  # 05:00 GMT+7
    assert is_late_night(datetime(2026, 1, 1, 21, 59, tzinfo=utc))  # 04:59 GMT+7
    assert is_late_night(datetime(2026, 1, 1, 23, 40))  # naive = GMT+7
    assert not is_late_night(None)
    assert not is_late_night(datetime(2026, 1, 1, 22, 59, tzinfo=timezone(timedelta(hours=7))))


def test_ui_hints_table() -> None:
    contact = TrustedContactRef(name="Con", phone="0900000000")
    full = Prefill(bank_bin="970418", account_number="1234567890", amount_vnd=1000)
    hints = compute_ui_hints(
        tier=DecisionTier.SOFT_FRICTION,
        reason_codes=["RC_COLD_START_NEEDS_CONTEXT"],
        cues=[Cue.URGENCY_TIME_PRESSURE],
        prefill=full,
        trusted_contacts=[contact],
        hotline="1900",
    )
    assert hints.calm_shield and hints.show_context_elicitation and hints.show_transfer_now
    assert hints.trusted_contacts == [contact] and hints.hotline == "1900"
    assert hints.missing_fields == []

    hard = compute_ui_hints(
        tier=DecisionTier.HARD_HOLD,
        reason_codes=[],
        prefill=Prefill(bank_bin="970418"),
        trusted_contacts=[contact],
        hotline="1900",
    )
    assert not hard.handoff_allowed and not hard.show_transfer_now
    assert hard.missing_fields == ["account_number", "amount_vnd"]
    assert not hard.calm_shield and hard.trusted_contacts == [] and hard.hotline is None

    assert compute_ui_hints(tier=DecisionTier.ALLOW, reason_codes=[], context="ONLINE_ORDER").safe_payment_tips
    assert compute_ui_hints(tier=DecisionTier.ALLOW, reason_codes=[], context="AUTHORITY_REQUEST").calm_shield
    night = datetime(2026, 1, 1, 23, 40)
    assert compute_ui_hints(tier=DecisionTier.SOFT_FRICTION, reason_codes=[], client_time=night).calm_shield
    assert not compute_ui_hints(tier=DecisionTier.ALLOW, reason_codes=[], client_time=night).calm_shield
