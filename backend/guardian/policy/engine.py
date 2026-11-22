"""PolicyEngine: pure rule functions at four trigger points (Flow A rules).

Triggers: ``before_call``, ``after_call`` (both used through ``ToolRunner``), ``before_emit`` and
``before_persist``. The engine only adds floors, stop codes and rule firings to the
``RequestContext``; it never lowers a tier and never reads free text (``memo`` is not an input).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from guardian.control_plane.session import RequestContext
from guardian.control_plane.tool_runner import ALLOWED_TOOLS, Abort, Allow, ToolNotAllowed
from guardian.policy import mapping
from guardian.policy.floors import Floor
from guardian.providers.base import PayerHistory, RecipientRisk, WalletDataProvider
from guardian.schemas.enums import DecisionTier, QrResult, ScamPlaybook, SourceIntegrity, StopCode
from guardian.schemas.extraction import FALLBACK_EXTRACTION, QuarantinedExtraction
from guardian.schemas.trace import RuleFiring
from guardian.stores.risk_memory import RiskMemoryEntry
from guardian.tools.pii import contact_name_variants, detect_pii

UNCONFIRMED_ACCOUNT_ABORTED = "UNCONFIRMED_ACCOUNT_ABORTED"
PII_EGRESS_ABORTED = "PII_EGRESS_BLOCKED"
RECIPIENT_RISK_TOOL = "lookup_recipient_risk_and_simo"
# Calls that send text to an LLM; R1 egress runs before each of them.
LLM_EGRESS_TOOLS = frozenset({"quarantined_extract", "plan"})
_EGRESS_TEXT_KEYS = ("text", "redacted_text", "tokenized_command")
_LLM_INVALID_STATUSES = frozenset({"INVALID_SCHEMA", "REFUSAL", "TRUNCATED", "NO_TOOL_CALL"})
_LLM_UNAVAILABLE_STATUSES = frozenset({"ERROR", "NOT_IMPLEMENTED", "SKIPPED"})


@dataclass(frozen=True)
class PersistDecision:
    """Outcome of ``before_persist`` (R1-consent, Law 91/2025)."""

    store_evidence: bool  # True: audit may carry ``evidence_redacted``
    hash_only: bool  # True: audit carries only ``content_sha256``
    stop_code: StopCode | None = None


class PolicyEngine:
    """Implements ``PolicyHooks`` plus the ``before_emit`` / ``before_persist`` triggers."""

    def __init__(
        self,
        fan_in_velocity_threshold: int = 10,
        wallet: WalletDataProvider | None = None,
        prefilter_soft_threshold: float = mapping.PREFILTER_SOFT_THRESHOLD,
    ) -> None:
        self._velocity_threshold = fan_in_velocity_threshold
        self._wallet = wallet
        self._prefilter_threshold = prefilter_soft_threshold

    def _contact_names(self, args: Mapping[str, Any]) -> tuple[str, ...] | None:
        """Names used by R1 egress; the same variants ``redact_pii_local`` is given."""
        explicit = args.get("contact_names")
        if explicit is not None:
            return tuple(explicit)
        if self._wallet is None:
            return None
        return contact_name_variants(self._wallet.contacts())

    # ------------------------------------------------------------------ helpers

    @staticmethod
    def _fire(
        ctx: RequestContext,
        rule: str,
        trigger: str,
        effect: str,
        floor: Floor | None = None,
        stop_code: StopCode | None = None,
    ) -> None:
        ctx.rules_fired.append(
            RuleFiring(
                rule=rule,
                trigger=trigger,  # type: ignore[arg-type]
                effect=effect,
                reason_code=floor.reason_code if floor else None,
                stop_code=stop_code.value if stop_code else None,
            )
        )

    def _add(self, ctx: RequestContext, floor: Floor, trigger: str, rule: str | None = None) -> None:
        ctx.floors.add(floor)
        self._fire(ctx, rule or floor.rule, trigger, "FLOOR_" + floor.tier.name, floor)

    # --------------------------------------------------------------- before_call

    def before_call(self, name: str, args: Mapping[str, Any], ctx: RequestContext) -> Allow | Abort:
        """Allowlist, then R2 (no recipient risk lookup for an unconfirmed OCR account)."""
        if name not in ALLOWED_TOOLS:
            self._fire(ctx, "ALLOWLIST", "before_call", "DENY")
            raise ToolNotAllowed(name)
        if name == RECIPIENT_RISK_TOOL and ctx.source_integrity == SourceIntegrity.OCR_UNCONFIRMED:
            floor = mapping.ocr_confirm_floor()
            stop = StopCode.ABORT_WAIT_NAPAS_NAME_USER_CONFIRM
            ctx.floors.add(floor)
            self._fire(ctx, "R2", "before_call", "ABORT", floor, stop)
            return Abort(stop_code=stop, result_code=UNCONFIRMED_ACCOUNT_ABORTED)
        if name in LLM_EGRESS_TOOLS:
            return self._check_egress(name, args, ctx)
        return Allow()

    def _check_egress(self, name: str, args: Mapping[str, Any], ctx: RequestContext) -> Allow | Abort:
        """R1 egress: any PII left in text bound for an LLM blocks the call (L4)."""
        names = self._contact_names(args)
        for key in _EGRESS_TEXT_KEYS:
            value = args.get(key)
            if isinstance(value, str) and detect_pii(value, contact_names=names):
                floor = mapping.pii_egress_floor()
                stop = StopCode.PII_EGRESS_BLOCKED
                ctx.floors.add(floor)
                self._fire(ctx, "R1", "before_call", "ABORT", floor, stop)
                return Abort(stop_code=stop, result_code=PII_EGRESS_ABORTED)
        return Allow()

    # --------------------------------------------------------------- after_call

    def after_call(self, name: str, result: Any, ctx: RequestContext) -> None:
        """TIER1 (QR), R4 (SIMO/GNN/velocity) and MEMORY floors from tool results."""
        if name == "verify_vietqr_emvco":
            qr_result = getattr(result, "result", None)
            if isinstance(qr_result, QrResult):
                floor = mapping.qr_floor(qr_result)
                if floor is not None:
                    self._add(ctx, floor, "after_call")
        elif name == RECIPIENT_RISK_TOOL and isinstance(result, RecipientRisk):
            self._apply_r4(result, ctx)
        elif name == "risk_memory_lookup" and isinstance(result, RiskMemoryEntry):
            self._add(ctx, mapping.memory_floor(), "after_call")
        elif name == "prompt_guard_cpu_score" and isinstance(result, (int, float)):
            self.apply_prefilter(float(result), ctx)
        elif name == "detect_hijack" and isinstance(result, bool):
            if result:
                self._add(ctx, mapping.hijack_floor(), "after_call")
        elif name == "check_urls" and isinstance(result, (list, tuple)):
            self.apply_urls(result, ctx)
        elif name == "quarantined_extract":
            self.apply_llm_outcome(ctx, result)

    # ------------------------------------------------------------ Flow B (after_call)

    def apply_prefilter(self, score: float, ctx: RequestContext) -> None:
        """S12 (R3 soft): prefilter score alone only raises SOFT_FRICTION."""
        if score >= self._prefilter_threshold:
            self._add(ctx, mapping.prefilter_floor(), "after_call")

    def apply_urls(self, results: Any, ctx: RequestContext) -> None:
        """S15 / S16 from URL_Checker results (objects with a ``flags`` collection)."""
        for floor in mapping.url_floors(getattr(r, "flags", ()) for r in results):
            self._add(ctx, floor, "after_call")

    def apply_llm_outcome(self, ctx: RequestContext, outcome: Any) -> QuarantinedExtraction | None:
        """L1-L3 and the extraction rows for a ``BreakerOutcome`` or ``LLMResult``.

        Returns the validated extraction when the call succeeded, else ``None``. Failures only
        add SOFT floors; the caller may follow up with ``apply_fallback_heuristic``.
        """
        status = getattr(outcome, "status", None)
        inner = getattr(outcome, "result", None) if hasattr(outcome, "result") else outcome
        if status == "OK" and inner is not None:  # BreakerOutcome wrapping an LLMResult
            status = getattr(inner, "status", None)
        value = getattr(inner, "value", None) if inner is not None else None

        if status == "OK" and isinstance(value, QuarantinedExtraction):
            self.apply_extraction(value, ctx)
            return value
        if status == "TIMEOUT":
            self._add(ctx, mapping.llm_timeout_floor(), "after_call")
        elif status in _LLM_UNAVAILABLE_STATUSES:
            self._add(ctx, mapping.llm_unavailable_floor(), "after_call")
        else:  # invalid schema, refusal, truncation, no tool call, or anything unexpected
            self._add(ctx, mapping.llm_invalid_floor(), "after_call")
            # The substitute extraction is UNKNOWN_SUSPICIOUS (P9, SOFT).
            for floor in mapping.fallback_floors(FALLBACK_EXTRACTION):
                self._add(ctx, floor, "after_call")
        return None

    def apply_extraction(self, extraction: QuarantinedExtraction, ctx: RequestContext) -> None:
        """S11, S13, P1-P9 and C1-C4 from a schema-valid extraction (never lowers a tier)."""
        if extraction.contains_prompt_injection:
            self._add(ctx, mapping.injection_floor(), "after_call")
        for floor in mapping.playbook_floors(extraction):
            self._add(ctx, floor, "after_call")
        for floor in mapping.cue_floors(extraction):
            self._add(ctx, floor, "after_call")

    def apply_fallback_heuristic(self, ctx: RequestContext, extraction: QuarantinedExtraction) -> None:
        """Keyword heuristic used when the LLM timed out, failed or was blocked.

        Only SOFT rows P8, P9, C3, C4 and X1 (account change request) may be emitted; it can never
        create HARD_HOLD.
        """
        for floor in mapping.fallback_floors(extraction):
            self._add(ctx, floor, "after_call")
        req = extraction.payment_request
        if req is not None and req.requests_account_change:
            self._add(ctx, mapping.account_swap_floor(), "after_call")

    # -------------------------------------------------------------- Flow B (emit)

    def before_emit_flow_b(
        self,
        ctx: RequestContext,
        *,
        extraction: QuarantinedExtraction | None,
        linked_account_digits: str | None = None,
        amount_vnd: int | None = None,
        total_24h_vnd: int = 0,
        risk: RecipientRisk | None = None,
        history: PayerHistory | None = None,
    ) -> bool:
        """Flow B emit rules: R6, R5, grey zone, X3, X1, then P10 last.

        ``extraction`` is ``None`` when no valid extraction exists (fallback path); P10 is then
        never added. Returns ``True`` when an account swap (X1) was detected. X4 (cold start) is
        Flow A only, so it is not added here.
        """
        if ctx.qr_present and not ctx.trace.has("verify_vietqr_emvco"):
            stop = StopCode.TEMPORAL_BYPASS_DETECTED_MISSING_VIETQR_CHECK
            ctx.floors.add(mapping.r6_floor())
            ctx.stop_codes.append(stop)
            self._fire(ctx, "R6", "before_emit", "FLOOR_HARD_HOLD", mapping.r6_floor(), stop)

        if amount_vnd is not None and mapping.is_structuring(amount_vnd, total_24h_vnd):
            self._add(ctx, mapping.structuring_floor(), "before_emit")

        if risk is not None and not self.has_r4_signal(risk):
            if (
                mapping.GNN_GREY_LOW <= risk.gnn_mule_score < mapping.GNN_HARD_THRESHOLD
                or risk.account_age_days < mapping.GREY_ACCOUNT_AGE_DAYS
            ):
                self._add(ctx, mapping.grey_zone_floor(), "before_emit")

        if history is not None and history.has_history:
            self._add(ctx, mapping.trusted_payee_floor(), "before_emit")

        swap = False
        if extraction is not None and extraction.payment_request is not None:
            req = extraction.payment_request
            extracted = req.account_digits_raw
            swap = req.requests_account_change or (
                linked_account_digits is not None
                and extracted is not None
                and extracted != linked_account_digits
            )
        if swap:
            self._add(ctx, mapping.account_swap_floor(), "before_emit")

        if (
            extraction is not None
            and extraction.scam_playbook == ScamPlaybook.NONE_DETECTED
            and ctx.floors.final_tier == DecisionTier.ALLOW
        ):
            self._add(ctx, mapping.no_scam_signal_floor(), "before_emit")
        return swap

    def _apply_r4(self, risk: RecipientRisk, ctx: RequestContext) -> None:
        if risk.simo_hit:
            self._add(ctx, mapping.simo_floor(), "after_call")
        if risk.gnn_mule_score >= mapping.GNN_HARD_THRESHOLD:
            self._add(ctx, mapping.gnn_floor(), "after_call")
        if risk.fan_in_senders_per_hour >= self._velocity_threshold:
            self._add(ctx, mapping.velocity_floor(), "after_call")

    def has_r4_signal(self, risk: RecipientRisk) -> bool:
        return (
            risk.simo_hit
            or risk.gnn_mule_score >= mapping.GNN_HARD_THRESHOLD
            or risk.fan_in_senders_per_hour >= self._velocity_threshold
        )

    # --------------------------------------------------------------- before_emit

    def before_emit(
        self,
        ctx: RequestContext,
        *,
        amount_vnd: int,
        total_24h_vnd: int = 0,
        risk: RecipientRisk | None = None,
        history: PayerHistory | None = None,
    ) -> None:
        """Flow A emit-time rules in the fixed order: R6, R5, grey zone, baseline.

        ``total_24h_vnd`` is the provider history total plus the session Ledger total.
        ``memo`` is deliberately not a parameter.
        """
        # 1. R6: QR payload present but never verified.
        if ctx.qr_present and not ctx.trace.has("verify_vietqr_emvco"):
            stop = StopCode.TEMPORAL_BYPASS_DETECTED_MISSING_VIETQR_CHECK
            ctx.floors.add(mapping.r6_floor())
            ctx.stop_codes.append(stop)
            self._fire(ctx, "R6", "before_emit", "FLOOR_HARD_HOLD", mapping.r6_floor(), stop)

        # 2. R5: structuring under Circular 50.
        if mapping.is_structuring(amount_vnd, total_24h_vnd):
            self._add(ctx, mapping.structuring_floor(), "before_emit")

        # 3. Grey zone: only when no S5-S7 signal fired.
        if risk is not None and not self.has_r4_signal(risk):
            grey = (
                mapping.GNN_GREY_LOW <= risk.gnn_mule_score < mapping.GNN_HARD_THRESHOLD
                or risk.account_age_days < mapping.GREY_ACCOUNT_AGE_DAYS
            )
            if grey:
                self._add(ctx, mapping.grey_zone_floor(), "before_emit")

        # 4. Baseline. X3 is added whenever history exists; X4 only when nothing exceeds ALLOW.
        if history is not None:
            if history.has_history:
                self._add(ctx, mapping.trusted_payee_floor(), "before_emit")
            elif ctx.floors.final_tier == DecisionTier.ALLOW:
                self._add(ctx, mapping.cold_start_floor(), "before_emit")

    # ------------------------------------------------------------ before_persist

    def before_persist(self, ctx: RequestContext, *, wants_evidence: bool = False) -> PersistDecision:
        """R1-consent: without consent only a hash may be stored; asking for evidence stops."""
        if ctx.explicit_consent_flag:
            return PersistDecision(store_evidence=True, hash_only=False)
        if wants_evidence:
            stop = StopCode.LAW_91_CONSENT_REQUIRED
            ctx.stop_codes.append(stop)
            self._fire(ctx, "R1", "before_persist", "STOP", None, stop)
            return PersistDecision(store_evidence=False, hash_only=True, stop_code=stop)
        return PersistDecision(store_evidence=False, hash_only=True)
