# Feature: momo-guardian-web, Property 6: Bảng quyết định Flow A
"""Property 6: Bảng quyết định Flow A.

**Validates: Requirements 4.11, 4.12, 6.5, 6.6, 6.7, 6.8, 6.9, 6.10, 8.2**
"""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

from hypothesis import given
from hypothesis import strategies as st

from guardian.config import Settings
from guardian.control_plane.flow_a import FlowAGate
from guardian.control_plane.pending_confirm import PendingConfirmStore
from guardian.control_plane.verdict_store import VerdictStore
from guardian.policy import mapping
from guardian.policy.engine import PolicyEngine
from guardian.providers.base import NameInquiryResult, PayerHistory, RecipientRisk
from guardian.providers.sandbox_wallet import SandboxWalletProvider
from guardian.providers.fixture_loader import resolve_fixtures_dir
from guardian.reason_codes import (
    RC_CIRCULAR50_STRUCTURING_RISK,
    RC_COLD_START_NEEDS_CONTEXT,
    RC_SIMO_OR_MULE_HIGH_RISK,
    RC_TRUSTED_PAYEE_HISTORY,
)
from guardian.schemas.api_models import FlowACheckRequest
from guardian.schemas.enums import DecisionTier, QrResult, SourceIntegrity
from guardian.stores.audit import AuditLog
from guardian.stores.ledger import Ledger
from guardian.stores.risk_memory import RiskMemory
from guardian.stores.shield_stats import ShieldStats
from guardian.tools.vietqr import crc16_ccitt_false, encode_vietqr
from tests.property.strategies.vietqr import accounts, valid_bins

VELOCITY_THRESHOLD = 10
_AUDIT_PATH = Path(tempfile.mkdtemp(prefix="p06_")) / "audit.jsonl"
_WALLET = SandboxWalletProvider(resolve_fixtures_dir(Settings(_env_file=None).fixtures_dir))


class _StubRisk:
    """Deterministic RiskDataProvider driven by the generated signals."""

    def __init__(self, risk: RecipientRisk, history: PayerHistory) -> None:
        self._risk, self._history = risk, history

    async def name_inquiry(self, bank_bin: str, account_number: str) -> NameInquiryResult:
        return NameInquiryResult(found=False)

    async def recipient_risk(self, bank_bin: str, account_number: str, amount_vnd: int) -> RecipientRisk:
        return self._risk

    async def payer_history(self, payer_session_hash: str, bank_bin: str, account_number: str) -> PayerHistory:
        return self._history


def _qr_payload(kind: str, bank_bin: str, account: str) -> str | None:
    if kind == "NONE":
        return None
    valid = encode_vietqr(bank_bin, account, None, "")
    if kind == "VALID_VIETQR":
        return valid
    if kind == "BAD_CRC":
        body, crc = valid[:-4], valid[-4:]
        return body + ("0000" if crc != "0000" else "0001")
    if kind == "FOREIGN_OR_NON_VND":
        body = valid[:-4].replace("5303704", "5303840")
        return f"{body}{crc16_ccitt_false(body):04X}"
    return "garbage-not-a-vietqr"  # INVALID_FORMAT


_QR_KINDS = ["NONE", "VALID_VIETQR", "BAD_CRC", "FOREIGN_OR_NON_VND", "INVALID_FORMAT"]

_amounts = st.one_of(
    st.integers(min_value=1, max_value=50_000_000),
    st.integers(min_value=8_900_000, max_value=10_100_000),
)
_gnn = st.one_of(
    st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
    st.sampled_from([0.0, 0.59, 0.6, 0.84, 0.85, 0.86, 1.0]),
)


@given(
    simo=st.booleans(),
    gnn=_gnn,
    fan_in=st.one_of(st.integers(0, 30), st.sampled_from([9, 10, 11])),
    age=st.one_of(st.integers(0, 400), st.sampled_from([29, 30, 31])),
    has_history=st.booleans(),
    total_24h=st.one_of(st.integers(0, 30_000_000), st.sampled_from([10_999_999, 11_000_000, 11_000_001])),
    amount=_amounts,
    qr_kind=st.sampled_from(_QR_KINDS),
    bank_bin=valid_bins,
    account=accounts,
)
def test_flow_a_decision_table(
    simo, gnn, fan_in, age, has_history, total_24h, amount, qr_kind, bank_bin, account
) -> None:
    risk = RecipientRisk(
        simo_hit=simo,
        gnn_mule_score=gnn,
        fan_in_senders_per_hour=fan_in,
        account_age_days=age,
        found=True,
    )
    history = PayerHistory(has_history=has_history, total_24h_vnd=total_24h)
    gate = FlowAGate(
        risk_provider=_StubRisk(risk, history),
        wallet_provider=_WALLET,
        risk_memory=RiskMemory(),
        ledger=Ledger(),
        verdict_store=VerdictStore(),
        pending_confirm=PendingConfirmStore(),
        audit=AuditLog(_AUDIT_PATH),
        shield_stats=ShieldStats(),
        policy=PolicyEngine(VELOCITY_THRESHOLD),
        session_secret="p06-secret",
    )
    req = FlowACheckRequest(
        bank_bin=bank_bin,
        account_number=account,
        amount_vnd=amount,
        source_integrity=SourceIntegrity.USER_TYPED,
        qr_payload=_qr_payload(qr_kind, bank_bin, account),
    )
    result = asyncio.run(gate.check("6f1c1d0e-7a3b-4c52-9d4e-0a1b2c3d4e5f", req))
    verdict = result.response.verdict
    codes = set(verdict.reason_codes)
    tier = verdict.decision_tier

    simo_sig = simo
    gnn_sig = gnn >= 0.85
    vel_sig = fan_in >= VELOCITY_THRESHOLD
    r4 = simo_sig or gnn_sig or vel_sig
    r5 = mapping.is_structuring(amount, total_24h)
    grey = (0.6 <= gnn < 0.85) or age < 30
    qr_hard = qr_kind == "BAD_CRC"
    qr_soft = qr_kind in ("FOREIGN_OR_NON_VND", "INVALID_FORMAT")

    if simo_sig:
        assert tier == DecisionTier.HARD_HOLD
        assert RC_SIMO_OR_MULE_HIGH_RISK in codes
        assert verdict.cooling_off_seconds == 60
    if gnn_sig:
        assert tier == DecisionTier.HARD_HOLD
        assert RC_SIMO_OR_MULE_HIGH_RISK in codes
    if vel_sig or qr_hard:
        assert tier == DecisionTier.HARD_HOLD
    if r5:
        assert tier >= DecisionTier.SOFT_FRICTION
        assert RC_CIRCULAR50_STRUCTURING_RISK in codes or len(codes) == 6
        assert verdict.cooling_off_seconds >= 30
    if grey and not r4 and not qr_hard:
        assert tier >= DecisionTier.SOFT_FRICTION
        assert len(verdict.system2_check_questions) >= 1
    if qr_soft:
        assert tier >= DecisionTier.SOFT_FRICTION

    no_signal = not (r4 or r5 or grey or qr_hard or qr_soft)
    if no_signal and has_history:
        assert tier == DecisionTier.ALLOW
        assert RC_TRUSTED_PAYEE_HISTORY in codes
    if no_signal and not has_history:
        assert tier == DecisionTier.SOFT_FRICTION
        assert RC_COLD_START_NEEDS_CONTEXT in codes


def test_qr_helper_kinds_verify_as_labelled() -> None:
    """Guard the generator: each QR kind verifies to the result the property assumes."""
    from guardian.tools.vietqr import verify_vietqr_emvco

    expected = {
        "VALID_VIETQR": QrResult.VALID_VIETQR,
        "BAD_CRC": QrResult.BAD_CRC,
        "FOREIGN_OR_NON_VND": QrResult.FOREIGN_OR_NON_VND,
        "INVALID_FORMAT": QrResult.INVALID_FORMAT,
    }
    for kind, result in expected.items():
        payload = _qr_payload(kind, "970422", "123456789")
        assert payload is not None
        assert verify_vietqr_emvco(payload).result == result
