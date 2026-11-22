"""FlowAGate: the payment-time gate. Rules and deterministic data only, never an LLM.

The constructor deliberately has no ``LLMClient`` parameter and this module must not import
``guardian.llm`` (checked by a test). ``memo`` is never passed to any rule; it is only stored in
the VerdictStore for the later bank hand-off.
"""

from __future__ import annotations

import hmac
import time
import uuid
from dataclasses import dataclass
from typing import Any

from guardian.control_plane.pending_confirm import PendingConfirmStore
from guardian.control_plane.session import RequestContext
from guardian.control_plane.tool_runner import ToolRunner
from guardian.control_plane.verdict_store import VerdictStore, VerdictTx
from guardian.policy.composer import ComposedVerdict, compose_verdict
from guardian.policy.engine import RECIPIENT_RISK_TOOL, PolicyEngine
from guardian.policy.floors import Floor, FloorSet
from guardian.policy.ui_hints import compute_ui_hints
from guardian.reason_codes import (
    RC_COLD_START_NEEDS_CONTEXT,
    RC_CONTEXT_AUTHORITY_DECLARED,
    RC_CONTEXT_IN_STORE_DECLARED,
    RC_CONTEXT_ONLINE_ORDER_DECLARED,
    RC_CONTEXT_RELATIVE_URGENT_DECLARED,
    RC_FAST_UNBLOCK_VERIFIED,
)
from guardian.providers.base import PayerHistory, RecipientRisk, WalletDataProvider
from guardian.providers.base import RiskDataProvider
from guardian.providers.clock import Clock, SystemClock
from guardian.schemas.api_models import (
    Channel,
    CheckResponse,
    ContextChoice,
    ContextRequest,
    NameConfirmation,
    FastUnblockRequest,
    FlowACheckRequest,
    QrVerifyResponse,
    StageTimings,
    TrustedContactRef,
)
from guardian.schemas.enums import DecisionTier, SourceIntegrity, StopCode
from guardian.schemas.trace import RuleFiring
from guardian.stores.audit import AuditLog, apply_consent
from guardian.stores.ledger import Ledger
from guardian.stores.risk_memory import RiskMemory
from guardian.stores.shield_stats import ShieldStats
from guardian.tools.vietqr import QrVerification, verify_vietqr_emvco

SANDBOX_SOURCES = ["NAPAS", "SIMO", "GNN"]
SANDBOX_OTP = "123456"


class VerdictNotFound(Exception):
    """The verdict_id is unknown, expired or owned by another session."""


class IdentityCheckFailed(Exception):
    """Wrong sandbox OTP."""


class FastUnblockNotAllowed(Exception):
    """The original verdict does not allow fast unblock."""


class ContextNotApplicable(Exception):
    """The original verdict does not contain RC_COLD_START_NEEDS_CONTEXT."""


_CONTEXT_FLOORS: dict[str, tuple[DecisionTier, str, str | None]] = {
    "IN_STORE": (DecisionTier.ALLOW, RC_CONTEXT_IN_STORE_DECLARED, None),
    "ONLINE_ORDER": (DecisionTier.SOFT_FRICTION, RC_CONTEXT_ONLINE_ORDER_DECLARED, None),
    "URGENT_RELATIVE": (
        DecisionTier.SOFT_FRICTION,
        RC_CONTEXT_RELATIVE_URGENT_DECLARED,
        "DEEPFAKE_RELATIVE_EMERGENCY",
    ),
    "AUTHORITY_REQUEST": (
        DecisionTier.SOFT_FRICTION,
        RC_CONTEXT_AUTHORITY_DECLARED,
        "IMPERSONATE_AUTHORITY_VNEID",
    ),
}


@dataclass(frozen=True)
class FlowAResult:
    response: CheckResponse
    verdict_id: str


class FlowAGate:
    def __init__(
        self,
        *,
        risk_provider: RiskDataProvider,
        wallet_provider: WalletDataProvider,
        risk_memory: RiskMemory,
        ledger: Ledger,
        verdict_store: VerdictStore,
        pending_confirm: PendingConfirmStore,
        audit: AuditLog,
        shield_stats: ShieldStats,
        policy: PolicyEngine,
        session_secret: str,
        hotline: str | None = None,
        clock: Clock | None = None,
    ) -> None:
        self._risk = risk_provider
        self._wallet = wallet_provider
        self._memory = risk_memory
        self._ledger = ledger
        self._verdicts = verdict_store
        self._pending = pending_confirm
        self._audit = audit
        self._stats = shield_stats
        self._policy = policy
        self._secret = session_secret
        self._hotline = hotline
        self._clock: Clock = clock or SystemClock()
        self._runner = ToolRunner(
            {
                "verify_vietqr_emvco": self._t_verify_qr,
                "risk_memory_lookup": self._t_memory,
                RECIPIENT_RISK_TOOL: self._t_recipient_risk,
                "lookup_payer_history": self._t_payer_history,
            },
            policy,
        )

    # ------------------------------------------------------------------ tools

    @staticmethod
    def _t_verify_qr(_ctx: RequestContext, *, payload: str) -> QrVerification:
        return verify_vietqr_emvco(payload)

    def _t_memory(self, ctx: RequestContext, *, bank_bin: str, account: str) -> Any:
        return self._memory.lookup_account(ctx.session_id, bank_bin, account)

    async def _t_recipient_risk(
        self, _ctx: RequestContext, *, bank_bin: str, account: str, amount_vnd: int
    ) -> RecipientRisk:
        return await self._risk.recipient_risk(bank_bin, account, amount_vnd)

    async def _t_payer_history(
        self, ctx: RequestContext, *, bank_bin: str, account: str
    ) -> PayerHistory:
        return await self._risk.payer_history(ctx.payer_session_hash, bank_bin, account)

    # ------------------------------------------------------------------ D4

    def resolve_source_integrity(
        self, session_id: str, req: FlowACheckRequest
    ) -> SourceIntegrity:
        """Never trust the client's claim of OCR confirmation without a matching token."""
        claimed = req.source_integrity
        if claimed == SourceIntegrity.OCR_CONFIRMED_BY_USER:
            if self._pending.validate_token(
                req.confirmation_token, session_id, req.bank_bin, req.account_number
            ):
                return claimed
            return SourceIntegrity.OCR_UNCONFIRMED
        if claimed == SourceIntegrity.VALID_VIETQR_CRC and req.qr_payload is None:
            return SourceIntegrity.USER_TYPED
        return claimed

    # ------------------------------------------------------------------ check

    async def check(self, session_id: str, req: FlowACheckRequest) -> FlowAResult:
        started = time.perf_counter()
        ctx = RequestContext.create(
            session_id,
            "FLOW_A",
            self._secret,
            request_id=f"req_{uuid.uuid4().hex[:16]}",
            client_time=req.client_time,
            debug=req.debug,
        )
        ctx.source_integrity = self.resolve_source_integrity(session_id, req)
        ctx.qr_present = req.qr_payload is not None
        skip_qr = bool(req.debug and req.debug.simulate_skip_qr_verify)

        qr: QrVerification | None = None
        if req.qr_payload is not None and not skip_qr:
            outcome = await self._runner.call("verify_vietqr_emvco", ctx, payload=req.qr_payload)
            qr = outcome.result

        risk: RecipientRisk | None = None
        history: PayerHistory | None = None
        risk_outcome = None
        if ctx.source_integrity == SourceIntegrity.OCR_UNCONFIRMED:
            # R2: the policy aborts this call; nothing about the recipient is looked up.
            risk_outcome = await self._runner.call(
                RECIPIENT_RISK_TOOL,
                ctx,
                bank_bin=req.bank_bin,
                account=req.account_number,
                amount_vnd=req.amount_vnd,
            )
        else:
            await self._runner.call(
                "risk_memory_lookup", ctx, bank_bin=req.bank_bin, account=req.account_number
            )
            risk_outcome = await self._runner.call(
                RECIPIENT_RISK_TOOL,
                ctx,
                bank_bin=req.bank_bin,
                account=req.account_number,
                amount_vnd=req.amount_vnd,
            )
            risk = risk_outcome.result
            history = (
                await self._runner.call(
                    "lookup_payer_history",
                    ctx,
                    bank_bin=req.bank_bin,
                    account=req.account_number,
                )
            ).result

        provider_total = history.total_24h_vnd if history is not None else 0
        self._policy.before_emit(
            ctx,
            amount_vnd=req.amount_vnd,
            total_24h_vnd=provider_total + self._ledger.total_24h(session_id),
            risk=risk,
            history=history,
        )

        composed: ComposedVerdict = compose_verdict(
            ctx.floors,
            origin_ocr=ctx.source_integrity == SourceIntegrity.OCR_UNCONFIRMED,
        )
        verdict = composed.verdict
        tier = ctx.floors.final_tier

        record = self._verdicts.put(
            session_id=session_id,
            channel="FLOW_A",
            tier=tier,
            floors=FloorSet(ctx.floors.floors),
            tx=VerdictTx(bin=req.bank_bin, account=req.account_number, amount=req.amount_vnd),
            qr_payload=req.qr_payload,
            extra={
                "memo": req.memo,
                "source_integrity": ctx.source_integrity.value,
                "question_count": len(verdict.system2_check_questions),
            },
        )

        name_confirmation: NameConfirmation | None = None
        if ctx.source_integrity == SourceIntegrity.OCR_UNCONFIRMED:
            name_confirmation = await self._name_confirmation(ctx, req)

        trusted = [
            TrustedContactRef(name=c.name, phone=c.phone) for c in self._wallet.trusted_contacts()
        ]
        hints = compute_ui_hints(
            tier=tier,
            reason_codes=verdict.reason_codes,
            client_time=req.client_time,
            trusted_contacts=trusted,
            hotline=self._hotline,
        )

        stop_codes: list[StopCode] = list(dict.fromkeys(ctx.stop_codes))
        persist = self._policy.before_persist(ctx)
        self._write_audit(ctx, record.verdict_id, verdict, composed, persist.hash_only)
        self._stats.record(session_id, tier)

        latency_ms = int((time.perf_counter() - started) * 1000)
        response = CheckResponse(
            request_id=ctx.request_id,
            verdict_id=record.verdict_id,
            channel="FLOW_A",
            verdict=verdict,
            ui_hints=hints,
            qr=QrVerifyResponse(**qr.to_dict()) if qr is not None else None,
            name_confirmation=name_confirmation,
            sandbox_sources=SANDBOX_SOURCES if risk is not None else [],
            trace=ctx.trace.steps,
            rules_fired=list(ctx.rules_fired),
            stop_codes=stop_codes,
            stage_timings_ms=StageTimings(total=latency_ms),
            latency_ms=latency_ms,
        )
        return FlowAResult(response=response, verdict_id=record.verdict_id)

    async def _name_confirmation(
        self, ctx: RequestContext, req: FlowACheckRequest
    ) -> NameConfirmation | None:
        """R2 abort: read-only NAPAS name lookup so the user can confirm the account."""
        try:
            name = await self._risk.name_inquiry(req.bank_bin, req.account_number)
        except Exception:  # noqa: BLE001 - the verdict stands without a name
            return None
        pending = self._pending.create(
            ctx.session_id,
            req.bank_bin,
            req.account_number,
            floors_snapshot=FloorSet(ctx.floors.floors),
        )
        self._pending.update(pending.pending_id, extra={"amount_vnd": req.amount_vnd, "origin": "OCR"})
        return NameConfirmation(
            pending_id=pending.pending_id,
            display_name=name.display_name,
            bank_name=name.bank_name,
            account_digits_spaced=" ".join(req.account_number),
            found=name.found,
            sandbox=name.sandbox,
        )

    # ------------------------------------------------------------------ follow-ups

    def _derive(
        self,
        session_id: str,
        origin: Any,
        channel: Channel,
        floors: FloorSet,
        *,
        context: ContextChoice | None = None,
        context_playbook: str | None = None,
        audit_extra: dict[str, Any],
        rule: RuleFiring,
        started: float,
    ) -> CheckResponse:
        """Compose, store, audit and wrap a verdict derived from an earlier Flow A verdict."""
        ctx = RequestContext.create(
            session_id,
            channel,
            self._secret,
            request_id=f"req_{uuid.uuid4().hex[:16]}",
        )
        ctx.floors = floors
        ctx.rules_fired.append(rule)
        composed = compose_verdict(floors, context_playbook=context_playbook)
        verdict = composed.verdict
        tier = floors.final_tier
        record = self._verdicts.put(
            session_id=session_id,
            channel=channel,
            tier=tier,
            floors=FloorSet(floors.floors),
            tx=origin.tx,
            qr_payload=origin.qr_payload,
            extra={
                **origin.extra,
                "origin_verdict_id": origin.verdict_id,
                "question_count": len(verdict.system2_check_questions),
            },
        )
        trusted = [
            TrustedContactRef(name=c.name, phone=c.phone) for c in self._wallet.trusted_contacts()
        ]
        hints = compute_ui_hints(
            tier=tier,
            reason_codes=verdict.reason_codes,
            context=context,
            trusted_contacts=trusted,
            hotline=self._hotline,
        )
        self._write_audit(ctx, record.verdict_id, verdict, composed, False, extra=audit_extra)
        latency_ms = int((time.perf_counter() - started) * 1000)
        return CheckResponse(
            request_id=ctx.request_id,
            verdict_id=record.verdict_id,
            channel=channel,
            verdict=verdict,
            ui_hints=hints,
            sandbox_sources=[],
            trace=ctx.trace.steps,
            rules_fired=list(ctx.rules_fired),
            stage_timings_ms=StageTimings(total=latency_ms),
            latency_ms=latency_ms,
        )

    def fast_unblock(self, session_id: str, req: FastUnblockRequest) -> CheckResponse:
        started = time.perf_counter()
        if not hmac.compare_digest(req.identity_check.code, SANDBOX_OTP):
            raise IdentityCheckFailed
        origin = self._verdicts.get(req.verdict_id, session_id)
        if origin is None:
            raise VerdictNotFound
        if not origin.floors.allow_fast_unblock():
            raise FastUnblockNotAllowed
        original_codes = [f.reason_code for f in origin.floors.floors]
        floors = FloorSet(origin.floors.floors)
        removed = floors.remove_removable("FAST_UNBLOCK")
        floors.add(Floor(DecisionTier.SOFT_FRICTION, RC_FAST_UNBLOCK_VERIFIED, "FAST_UNBLOCK"))
        extra = {
            "original_reason_codes": list(dict.fromkeys(original_codes)),
            "purpose": req.purpose,
            "unblocked_at": self._clock.now().isoformat(),
        }
        rule = RuleFiring(
            rule="FAST_UNBLOCK",
            trigger="before_emit",
            effect=f"removed_floors={len(removed)}",
            reason_code=RC_FAST_UNBLOCK_VERIFIED,
        )
        return self._derive(
            session_id,
            origin,
            "FAST_UNBLOCK",
            floors,
            audit_extra=extra,
            rule=rule,
            started=started,
        )

    def apply_context(self, session_id: str, req: ContextRequest) -> CheckResponse:
        started = time.perf_counter()
        origin = self._verdicts.get(req.verdict_id, session_id)
        if origin is None:
            raise VerdictNotFound
        codes = [f.reason_code for f in origin.floors.floors]
        if RC_COLD_START_NEEDS_CONTEXT not in codes:
            raise ContextNotApplicable
        tier, code, playbook = _CONTEXT_FLOORS[req.context]
        floors = FloorSet(origin.floors.floors)
        if req.context == "IN_STORE":
            floors.remove_removable("CONTEXT_IN_STORE")
        else:
            # The declared context replaces the cold-start floor at an equal tier (never lowers it).
            floors = FloorSet(f for f in origin.floors.floors if f.rule != "COLD_START")
        floors.add(Floor(tier, code, "CONTEXT"))
        extra = {
            "original_reason_codes": list(dict.fromkeys(codes)),
            "purpose": None,
            "context": req.context,
        }
        rule = RuleFiring(
            rule="CONTEXT", trigger="before_emit", effect=req.context.lower(), reason_code=code
        )
        return self._derive(
            session_id,
            origin,
            "CONTEXT",
            floors,
            context=req.context,
            context_playbook=playbook,
            audit_extra=extra,
            rule=rule,
            started=started,
        )

    # ------------------------------------------------------------------ audit

    def _write_audit(
        self,
        ctx: RequestContext,
        verdict_id: str,
        verdict: Any,
        composed: ComposedVerdict,
        hash_only: bool,
        extra: dict[str, Any] | None = None,
    ) -> None:
        record: dict[str, Any] = {
            "ts": self._clock.now().isoformat(),
            "audit_id": f"au_{uuid.uuid4().hex[:16]}",
            "request_id": ctx.request_id,
            "verdict_id": verdict_id,
            "channel": ctx.channel,
            "session_hash": ctx.payer_session_hash,
            "llm_provider": None,
            "decision_tier": ctx.floors.final_tier.name,
            "reason_codes": list(verdict.reason_codes),
            "reason_codes_truncated": list(composed.overflow_reason_codes),
            "rules_fired": [r.model_dump() for r in ctx.rules_fired],
            "stop_codes": [s.value for s in dict.fromkeys(ctx.stop_codes)],
            "trace": [s.model_dump() for s in ctx.trace.steps],
            "reasoning_summary": None,
            "extra": extra or {"original_reason_codes": None, "purpose": None},
        }
        record = apply_consent(
            record,
            explicit_consent_flag=ctx.explicit_consent_flag and not hash_only,
            original=None,
            redacted_text=None,
        )
        self._audit.append(record)
