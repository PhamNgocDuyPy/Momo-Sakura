"""FlowBOrchestrator: Untrusted_Content analysis (paste, OCR, QR, share).

Fixed order (design.md, Req 17.7): label_untrusted -> redact_pii_local -> scan_entities ->
detect_hijack -> verify_vietqr_emvco (if QR) -> check_urls -> napas_name_inquiry_readonly (OCR) or
lookup_recipient_risk_and_simo + risk_memory_lookup -> [prompt_guard_cpu_score || quarantined_extract
through the CircuitBreaker] -> before_emit -> compose -> before_persist -> audit.

Every tool goes through ``ToolRunner``. The LLM only sees PII-redacted text, never calls a tool and
can only raise the tier. Any unexpected failure ends in a SOFT fallback verdict, never ALLOW.
This module has no HTTP code; the NDJSON endpoint lives in ``api/flow_b.py``.
"""

from __future__ import annotations

import asyncio
import inspect
import time
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError

from guardian.control_plane import grounding
from guardian.control_plane.pending_confirm import PendingConfirmStore
from guardian.control_plane.session import RequestContext
from guardian.control_plane.tool_runner import ToolOutcome, ToolRunner
from guardian.control_plane.verdict_store import VerdictStore, VerdictTx
from guardian.features.promo_checker import check_promo, parse_official_promos
from guardian.features.shop_checker import check_listing, parse_reference_prices
from guardian.llm.base import LLMClient, LLMResult
from guardian.llm.circuit_breaker import CircuitBreaker
from guardian.llm.mock_rules import mock_extract
from guardian.policy import mapping
from guardian.policy.composer import ComposedVerdict, compose_verdict, ordered_reason_codes
from guardian.policy.engine import RECIPIENT_RISK_TOOL, PolicyEngine
from guardian.policy.floors import Floor, FloorSet
from guardian.policy.ui_hints import compute_ui_hints
from guardian.providers.base import NameInquiryResult, RecipientRisk, RiskDataProvider, WalletDataProvider
from guardian.providers.clock import Clock, SystemClock
from guardian.providers.sandbox_reference import ReferenceDataProvider
from guardian.schemas.api_models import (
    CheckResponse,
    DebugOverrides,
    Extensions,
    FlowBCheckRequest,
    FlowBStage2Event,
    ListingExtension,
    NameConfirmation,
    OfficialPromo,
    Prefill,
    PromoExtension,
    QrVerifyResponse,
    ReceiptExtension,
    ReceiptItemOut,
    RecipientRiskOut,
    Signals,
    StageTimings,
    TrustedContactRef,
    UiHints,
    UrlReport,
)
from guardian.schemas.enums import (
    AccountOrigin,
    ContentMode,
    ContentOrigin,
    DecisionTier,
    HardSource,
    QrResult,
    SourceIntegrity,
    StopCode,
)
from guardian.schemas.extraction import FALLBACK_EXTRACTION, QuarantinedExtraction
from guardian.schemas.trace import RuleFiring
from guardian.stores.audit import AuditLog, apply_consent
from guardian.stores.ledger import Ledger
from guardian.stores.risk_memory import RiskMemory, account_key, domain_key
from guardian.stores.shield_stats import ShieldStats
from guardian.tools.banks import bank_name, bin_for_alias
from guardian.tools.entity_scanner import scan_entities
from guardian.tools.hijack import detect_hijack
from guardian.tools.pii import contact_name_variants, redact_pii_local
from guardian.tools.prefilter import prompt_guard_cpu_score
from guardian.tools.url_checker import check_urls
from guardian.tools.vietqr import QrVerification, verify_vietqr_emvco

SANDBOX_SOURCES = ["NAPAS", "SIMO", "GNN"]
DEFAULT_LLM_TIMEOUT_MS = 4000
_MAX_ACCOUNTS = 3

# Floors produced by LLM output; excluded from the provisional (stage2) tier.
_LLM_RULES = frozenset({"PLAYBOOK", "CUE", "LLM_FALLBACK"})

_ORIGIN_TO_ACCOUNT_ORIGIN: dict[ContentOrigin, AccountOrigin] = {
    ContentOrigin.PASTE: AccountOrigin.PASTE,  # D3: pasted text is never "OCR"
    ContentOrigin.CLIPBOARD: AccountOrigin.CLIPBOARD,
    ContentOrigin.OCR: AccountOrigin.OCR,
    ContentOrigin.QR_CAMERA: AccountOrigin.QR,
    ContentOrigin.QR_IMAGE: AccountOrigin.QR,
    ContentOrigin.SHARE_TARGET: AccountOrigin.SHARE,
    ContentOrigin.CONTEXT_CHAT: AccountOrigin.PASTE,
    # Chrome extension text is untrusted page/selection text, handled exactly like PASTE.
    ContentOrigin.EXTENSION_SELECTION: AccountOrigin.PASTE,
    ContentOrigin.EXTENSION_PAGE_TEXT: AccountOrigin.PASTE,
}

Stage2Callback = Callable[[FlowBStage2Event], Awaitable[None] | None]


@dataclass(frozen=True)
class FlowBResult:
    response: CheckResponse
    verdict_id: str


@dataclass
class _Account:
    bank_bin: str | None
    digits: str


def _is_llm_floor(floor: Floor) -> bool:
    return floor.rule in _LLM_RULES or floor.hard_source == HardSource.PROMPT_INJECTION


def _tag62_text(qr: QrVerification | None) -> str:
    fields = qr.fields if qr is not None else None
    tag62 = fields.get("tag62") if isinstance(fields, dict) else None
    if not isinstance(tag62, dict):
        return ""
    return "\n".join(str(v) for v in tag62.values() if isinstance(v, str) and v)


class FlowBOrchestrator:
    def __init__(
        self,
        *,
        risk_provider: RiskDataProvider,
        wallet_provider: WalletDataProvider,
        reference_provider: ReferenceDataProvider,
        risk_memory: RiskMemory,
        verdict_store: VerdictStore,
        pending_confirm: PendingConfirmStore,
        audit: AuditLog,
        shield_stats: ShieldStats,
        policy: PolicyEngine,
        llm: LLMClient,
        session_secret: str,
        ledger: Ledger | None = None,
        hotline: str | None = None,
        clock: Clock | None = None,
        sandbox_clock: Clock | None = None,
        llm_timeout_ms: int = DEFAULT_LLM_TIMEOUT_MS,
        debug_enabled: bool = False,
        breaker: CircuitBreaker | None = None,
    ) -> None:
        self._risk = risk_provider
        self._wallet = wallet_provider
        self._reference = reference_provider
        self._memory = risk_memory
        self._verdicts = verdict_store
        self._pending = pending_confirm
        self._audit = audit
        self._stats = shield_stats
        self._policy = policy
        self._llm = llm
        self._secret = session_secret
        self._ledger = ledger
        self._hotline = hotline
        self._clock: Clock = clock or SystemClock()
        self._sandbox_clock: Clock = sandbox_clock or self._clock
        self._debug_enabled = debug_enabled
        self._breaker = breaker or CircuitBreaker(timeout_ms=llm_timeout_ms)
        self._runner = ToolRunner(
            {
                "redact_pii_local": self._t_redact,
                "scan_entities": lambda _ctx, *, text: scan_entities(text),
                "detect_hijack": lambda _ctx, *, text: detect_hijack(text),
                "verify_vietqr_emvco": lambda _ctx, *, payload: verify_vietqr_emvco(payload),
                "check_urls": lambda _ctx, *, text: check_urls(text),
                "napas_name_inquiry_readonly": self._t_name_inquiry,
                RECIPIENT_RISK_TOOL: self._t_recipient_risk,
                "risk_memory_lookup": self._t_memory_lookup,
                "risk_memory_write": self._t_memory_write,
                "prompt_guard_cpu_score": self._t_prefilter,
                "quarantined_extract": self._t_extract,
                "lookup_official_promos": self._t_promos,
                "lookup_reference_price": self._t_prices,
            },
            policy,
        )

    # ------------------------------------------------------------------ tools

    @staticmethod
    def _t_redact(
        _ctx: RequestContext, *, text: str, contact_names: tuple[str, ...], passthrough: bool
    ) -> tuple[str, dict[str, int]]:
        if passthrough:  # debug fault injection (T26): the redactor "fails" and leaks the text
            return text, {}
        return redact_pii_local(text, contact_names)

    async def _t_name_inquiry(
        self, _ctx: RequestContext, *, bank_bin: str, account: str
    ) -> NameInquiryResult:
        return await self._risk.name_inquiry(bank_bin, account)

    async def _t_recipient_risk(
        self, _ctx: RequestContext, *, bank_bin: str, account: str, amount_vnd: int
    ) -> RecipientRisk:
        return await self._risk.recipient_risk(bank_bin, account, amount_vnd)

    def _t_memory_lookup(
        self,
        ctx: RequestContext,
        *,
        bank_bin: str | None = None,
        account: str | None = None,
        domain: str | None = None,
    ) -> Any:
        if domain is not None:
            return self._memory.lookup_domain(ctx.session_id, domain)
        return self._memory.lookup_account(ctx.session_id, bank_bin, account or "")

    def _t_memory_write(self, ctx: RequestContext, *, key: str, reason_code: str) -> Any:
        return self._memory.write(ctx.session_id, key, reason_code)

    @staticmethod
    async def _t_prefilter(_ctx: RequestContext, *, text: str) -> float:
        return await asyncio.to_thread(prompt_guard_cpu_score, text)

    async def _t_extract(
        self,
        _ctx: RequestContext,
        *,
        redacted_text: str,
        mode: Any,
        contact_names: tuple[str, ...],
        delay_ms: int,
        forced: dict[str, Any] | None,
    ) -> Any:
        async def call() -> LLMResult[QuarantinedExtraction]:
            if delay_ms:
                await asyncio.sleep(delay_ms / 1000)
            if forced is not None:
                try:
                    return LLMResult(QuarantinedExtraction.model_validate(forced), "OK", "forced", 0)
                except ValidationError:
                    return LLMResult(None, "INVALID_SCHEMA", "forced", 0)
            return await self._llm.extract(redacted_text, mode)

        return await self._breaker.call(call)

    def _t_promos(self, _ctx: RequestContext) -> Any:
        return parse_official_promos(self._reference.official_promo_rows())

    def _t_prices(self, _ctx: RequestContext) -> Any:
        return parse_reference_prices(self._reference.reference_price_rows())

    # ------------------------------------------------------------------ helpers

    @staticmethod
    def _ms(started: float) -> int:
        return int((time.perf_counter() - started) * 1000)

    @staticmethod
    def _add_floor(ctx: RequestContext, floor: Floor, rule: str) -> None:
        ctx.floors.add(floor)
        ctx.rules_fired.append(
            RuleFiring(
                rule=rule,
                trigger="before_emit",
                effect="FLOOR_" + floor.tier.name,
                reason_code=floor.reason_code,
            )
        )

    @staticmethod
    def _add_account(accounts: list[_Account], bank_bin: str | None, digits: str | None) -> None:
        if not digits or len(accounts) >= _MAX_ACCOUNTS:
            return
        if any(a.digits == digits for a in accounts):
            return
        accounts.append(_Account(bank_bin, digits))

    def _resolve_debug(self, req: FlowBCheckRequest) -> DebugOverrides | None:
        return req.debug if self._debug_enabled else None

    # ------------------------------------------------------------------ entry point

    async def check(
        self,
        session_id: str,
        req: FlowBCheckRequest,
        *,
        on_stage2: Stage2Callback | None = None,
    ) -> FlowBResult:
        started = time.perf_counter()
        ctx = RequestContext.create(
            session_id,
            "FLOW_B",
            self._secret,
            request_id=f"req_{uuid.uuid4().hex[:16]}",
            client_time=req.client_time,
            debug=self._resolve_debug(req),
            explicit_consent_flag=req.explicit_consent_flag,
        )
        try:
            return await self._run(ctx, req, started, on_stage2)
        except Exception:  # noqa: BLE001 - never ALLOW on an unexpected failure
            return self._emergency(ctx, req, started)

    # ------------------------------------------------------------------ main pipeline

    async def _run(
        self,
        ctx: RequestContext,
        req: FlowBCheckRequest,
        started: float,
        on_stage2: Stage2Callback | None,
    ) -> FlowBResult:
        call = self._runner.call
        content = req.content
        text = content.text or ""
        qr_payload = content.qr_payload
        has_text = bool(text.strip())
        if not has_text and qr_payload is None:
            raise ValueError("EMPTY_CONTENT")
        qr_only = qr_payload is not None and not has_text
        debug = ctx.debug
        ctx.qr_present = qr_payload is not None
        ctx.source_integrity = SourceIntegrity.USER_TYPED  # D3: pasted account digits are exact

        # 1. label
        ctx.trace.record(
            "stage", "label_untrusted", "ok", {"origin": content.origin.value, "trust": "UNTRUSTED"}
        )

        # 2. redact (the same contact variants are used by the R1 egress check)
        names = contact_name_variants(self._wallet.contacts())
        redacted, counts = (
            await call(
                "redact_pii_local",
                ctx,
                text=text,
                contact_names=names,
                passthrough=bool(debug and debug.simulate_redactor_failure),
            )
        ).result
        for step in reversed(ctx.trace.steps):  # Req 13: trace shows redaction counts only, never values
            if step.name == "redact_pii_local" and step.status == "ok":
                step.detail = {"redacted": {str(k): int(v) for k, v in counts.items()}}
                break

        # 3-4. entities and hijack
        entities = (await call("scan_entities", ctx, text=text)).result
        await call("detect_hijack", ctx, text=text)

        # 5. QR
        qr: QrVerification | None = None
        if qr_payload is not None and not (debug and debug.simulate_skip_qr_verify):
            qr = (await call("verify_vietqr_emvco", ctx, payload=qr_payload)).result
        qr_valid = qr is not None and qr.result == QrResult.VALID_VIETQR

        # 6. URLs
        url_results = list((await call("check_urls", ctx, text=text)).result)

        # accounts under inspection
        accounts: list[_Account] = []
        if qr_valid and qr is not None and qr.fields:
            self._add_account(accounts, qr.fields.get("bank_bin"), qr.fields.get("account_number"))
        for mention in entities.accounts:
            self._add_account(accounts, mention.bank_bin, mention.account_number)

        is_ocr = content.origin == ContentOrigin.OCR
        if is_ocr and accounts:
            ctx.source_integrity = SourceIntegrity.OCR_UNCONFIRMED
        elif qr_valid:
            ctx.source_integrity = SourceIntegrity.VALID_VIETQR_CRC

        scan_amount = entities.amounts[0] if entities.amounts else None

        # 7. NAPAS name (OCR) or recipient risk + Risk_Memory
        risks: list[RecipientRisk] = []
        name_result: NameInquiryResult | None = None
        ocr_pending_account: _Account | None = None
        if ctx.source_integrity == SourceIntegrity.OCR_UNCONFIRMED:
            primary = accounts[0]
            if primary.bank_bin is not None:
                name_result = (
                    await call(
                        "napas_name_inquiry_readonly",
                        ctx,
                        bank_bin=primary.bank_bin,
                        account=primary.digits,
                    )
                ).result
                ocr_pending_account = primary
            # R2: the recipient is not looked up until the user confirms the name.
            self._add_floor(ctx, mapping.ocr_confirm_floor(), "R2")
            ctx.stop_codes.append(StopCode.ABORT_WAIT_NAPAS_NAME_USER_CONFIRM)
        else:
            for acct in accounts:
                await call("risk_memory_lookup", ctx, bank_bin=acct.bank_bin, account=acct.digits)
                if acct.bank_bin is not None:
                    risk = (
                        await call(
                            RECIPIENT_RISK_TOOL,
                            ctx,
                            bank_bin=acct.bank_bin,
                            account=acct.digits,
                            amount_vnd=scan_amount or 0,
                        )
                    ).result
                    if isinstance(risk, RecipientRisk):
                        risks.append(risk)
        for url in url_results:
            await call("risk_memory_lookup", ctx, domain=url.domain)

        # 8. prefilter (thread) in parallel with the quarantined extraction
        prefilter_text = "\n".join(p for p in (text, _tag62_text(qr)) if p)
        prefilter_task = asyncio.ensure_future(
            call("prompt_guard_cpu_score", ctx, text=prefilter_text)
        )
        llm_task: asyncio.Future[ToolOutcome] | None = None
        if qr_only:
            ctx.trace.record("llm", "quarantined_extract", "skipped", {"reason": "qr_only"})
        else:
            forced = debug.force_llm_output if debug else None
            delay_ms = debug.simulate_llm_delay_ms if debug and debug.simulate_llm_delay_ms else 0
            llm_task = asyncio.ensure_future(
                call(
                    "quarantined_extract",
                    ctx,
                    redacted_text=redacted,
                    mode=req.mode,
                    contact_names=names,
                    delay_ms=delay_ms,
                    forced=forced,
                )
            )
        try:
            prefilter_outcome = await prefilter_task
            prefilter_score = float(prefilter_outcome.result or 0.0)
            stage2_ms = self._ms(started)
            await self._emit_stage2(ctx, on_stage2, qr, url_results, prefilter_score, risks, stage2_ms)
            llm_outcome = await llm_task if llm_task is not None else None
        finally:
            for task in (prefilter_task, llm_task):
                if task is not None and not task.done():
                    task.cancel()
        llm_wait_ms = self._ms(started) - stage2_ms

        extraction = self._settle_llm(ctx, llm_outcome, redacted, req) if llm_task is not None else None

        # LLM-extracted account that the scan did not find: look it up too (never for OCR, R2)
        if extraction is not None and ctx.source_integrity != SourceIntegrity.OCR_UNCONFIRMED:
            await self._lookup_llm_entity(ctx, extraction, accounts, risks, scan_amount)

        # 9. before_emit: extensions (F3/F4/F5), then the Flow B rules
        extensions = await self._apply_extensions(ctx, req, extraction, url_results, redacted)
        pr = extraction.payment_request if extraction else None
        amount = (
            (pr.amount_vnd if pr else None)
            or (qr.fields.get("amount_vnd") if qr_valid and qr and qr.fields else None)
            or scan_amount
        )
        total_24h = self._ledger.total_24h(ctx.session_id) if self._ledger is not None else 0
        swap = self._policy.before_emit_flow_b(
            ctx,
            extraction=extraction,
            linked_account_digits=req.linked_transaction.account_number if req.linked_transaction else None,
            amount_vnd=amount,
            total_24h_vnd=total_24h,
            risk=risks[0] if risks else None,
        )
        if len(ctx.floors) == 0:  # QR only and clean: baseline so the verdict is never empty
            self._add_floor(ctx, mapping.no_scam_signal_floor(), "BASELINE")

        # compose
        composed: ComposedVerdict = compose_verdict(
            ctx.floors,
            extraction_playbook=extraction.scam_playbook.value if extraction else None,
            origin_ocr=ctx.source_integrity == SourceIntegrity.OCR_UNCONFIRMED,
            account_swap_detected=swap,
        )
        verdict = composed.verdict
        tier = ctx.floors.final_tier

        prefill = self._build_prefill(content.origin, ctx, accounts, extraction, qr, qr_valid, amount, redacted, req.linked_transaction
        )
        name_confirmation = self._store_pending(
            ctx, ocr_pending_account, name_result, extraction, amount, content.origin
        )

        record = self._verdicts.put(
            session_id=ctx.session_id,
            channel="FLOW_B",
            tier=tier,
            floors=FloorSet(ctx.floors.floors),
            tx=VerdictTx(
                bin=accounts[0].bank_bin if accounts else None,
                account=accounts[0].digits if accounts else None,
                amount=amount,
            ),
            qr_payload=qr_payload,
            extra={
                "origin": content.origin.value,
                "mode": req.mode.value,
                "source_integrity": ctx.source_integrity.value,
                "question_count": len(verdict.system2_check_questions),
            },
        )

        # before_persist (R1-consent), Risk_Memory handoff, audit
        persist = self._policy.before_persist(ctx)
        if tier == DecisionTier.HARD_HOLD:
            await self._write_risk_memory(ctx, composed, accounts, url_results)
        total_ms = self._ms(started)
        timings = StageTimings(stage2=stage2_ms, stage3=llm_wait_ms, total=total_ms)
        self._write_audit(
            ctx,
            record.verdict_id,
            composed,
            persist.hash_only,
            original=text or qr_payload,
            redacted=redacted,
            extraction=extraction,
            timings=timings,
            extra={"origin": content.origin.value, "mode": req.mode.value, "redaction_counts": counts},
        )
        self._stats.record(ctx.session_id, tier)

        cues = list(extraction.manipulation_cues) if extraction else []
        trusted = [
            TrustedContactRef(name=c.name, phone=c.phone) for c in self._wallet.trusted_contacts()
        ]
        hints: UiHints = compute_ui_hints(
            tier=tier,
            reason_codes=verdict.reason_codes,
            cues=cues,
            client_time=req.client_time,
            prefill=prefill,
            listing_requires_deposit=bool(
                extraction and extraction.listing and extraction.listing.requires_deposit
            ),
            trusted_contacts=trusted,
            hotline=self._hotline,
        )
        url_flags = sorted({f for r in url_results for f in r.flags})
        response = CheckResponse(
            request_id=ctx.request_id,
            verdict_id=record.verdict_id,
            channel="FLOW_B",
            verdict=verdict,
            ui_hints=hints,
            qr=QrVerifyResponse(**qr.to_dict()) if qr is not None else None,
            prefill=prefill,
            name_confirmation=name_confirmation,
            extensions=extensions,
            signals=Signals(
                scam_playbook=extraction.scam_playbook if extraction else None,
                manipulation_cues=cues,
                url_flags=url_flags,
                prefilter_score=min(1.0, max(0.0, prefilter_score)),
            ),
            sandbox_sources=SANDBOX_SOURCES if (risks or name_result is not None) else [],
            trace=ctx.trace.steps,
            rules_fired=list(ctx.rules_fired),
            stop_codes=list(dict.fromkeys(ctx.stop_codes)),
            stage_timings_ms=timings,
            latency_ms=total_ms,
        )
        return FlowBResult(response=response, verdict_id=record.verdict_id)

    # ------------------------------------------------------------------ stage 2 event

    async def _emit_stage2(
        self,
        ctx: RequestContext,
        callback: Stage2Callback | None,
        qr: QrVerification | None,
        url_results: list[Any],
        prefilter_score: float,
        risks: list[RecipientRisk],
        elapsed_ms: int,
    ) -> None:
        if callback is None:
            return
        deterministic = FloorSet(f for f in ctx.floors if not _is_llm_floor(f))
        event = FlowBStage2Event(
            request_id=ctx.request_id,
            provisional_tier=deterministic.final_tier.name,  # type: ignore[arg-type]
            provisional_reason_codes=ordered_reason_codes(deterministic)[:6],
            red_alert=(qr is not None and qr.result == QrResult.BAD_CRC)
            or any(r.simo_hit for r in risks),
            qr=QrVerifyResponse(**qr.to_dict()) if qr is not None else None,
            urls=[UrlReport(domain=u.domain, flags=sorted(u.flags)) for u in url_results],
            prefilter_score=min(1.0, max(0.0, prefilter_score)),
            recipient_risk=(
                RecipientRiskOut(
                    simo_hit=risks[0].simo_hit, gnn_mule_score=risks[0].gnn_mule_score
                )
                if risks
                else None
            ),
            elapsed_ms=elapsed_ms,
        )
        result = callback(event)
        if inspect.isawaitable(result):
            await result

    # ------------------------------------------------------------------ LLM outcome

    def _settle_llm(
        self,
        ctx: RequestContext,
        outcome: ToolOutcome | None,
        redacted: str,
        req: FlowBCheckRequest,
    ) -> QuarantinedExtraction | None:
        """Return the validated extraction, or apply the SOFT-only keyword heuristic."""
        extraction: QuarantinedExtraction | None = None
        status = "UNKNOWN"
        if outcome is not None and outcome.aborted:
            status = "ABORTED"  # R1 egress block (D8); the policy already added its floor
        elif outcome is not None:
            breaker_outcome = outcome.result
            status = str(getattr(breaker_outcome, "status", "UNKNOWN"))
            inner = getattr(breaker_outcome, "result", None)
            value = getattr(inner, "value", None)
            if status == "OK" and getattr(inner, "status", None) == "OK" and isinstance(
                value, QuarantinedExtraction
            ):
                extraction = value
            elif status == "OK":
                status = str(getattr(inner, "status", "UNKNOWN"))
        if extraction is None:
            ctx.trace.record("stage", "llm_fallback", "ok", {"cause": status})
            try:
                heuristic = mock_extract(redacted, req.mode)
            except Exception:  # noqa: BLE001
                heuristic = FALLBACK_EXTRACTION
            self._policy.apply_fallback_heuristic(ctx, heuristic)
        return extraction

    async def _lookup_llm_entity(
        self,
        ctx: RequestContext,
        extraction: QuarantinedExtraction,
        accounts: list[_Account],
        risks: list[RecipientRisk],
        scan_amount: int | None,
    ) -> None:
        pr = extraction.payment_request
        digits = (pr.account_digits_raw if pr else None) or extraction.extracted_entities.account_digits_raw
        if not digits or any(a.digits == digits for a in accounts) or len(accounts) >= _MAX_ACCOUNTS:
            return
        name = (pr.bank_bin_or_name if pr else None) or extraction.extracted_entities.bank_bin_or_name
        bank_bin = name if name and name.isdigit() and len(name) == 6 else (bin_for_alias(name) if name else None)
        accounts.append(_Account(bank_bin, digits))
        ctx.trace.record("stage", "llm_entity_lookup", "ok", {"reason": "llm_entity"})
        await self._runner.call("risk_memory_lookup", ctx, bank_bin=bank_bin, account=digits)
        if bank_bin is not None:
            risk = (
                await self._runner.call(
                    RECIPIENT_RISK_TOOL,
                    ctx,
                    bank_bin=bank_bin,
                    account=digits,
                    amount_vnd=(pr.amount_vnd if pr and pr.amount_vnd else scan_amount) or 0,
                )
            ).result
            if isinstance(risk, RecipientRisk):
                risks.append(risk)

    # ------------------------------------------------------------------ extensions F3/F4/F5

    async def _apply_extensions(
        self,
        ctx: RequestContext,
        req: FlowBCheckRequest,
        extraction: QuarantinedExtraction | None,
        url_results: list[Any],
        redacted: str,
    ) -> Extensions | None:
        if extraction is None:
            return None
        receipt = listing = promo = None
        cues = extraction.manipulation_cues

        if extraction.receipt_items is not None and (
            extraction.receipt_items.items or extraction.receipt_items.total_vnd is not None
        ):
            items = [
                ReceiptItemOut(
                    name=grounding.ground_string(i.name, redacted) or "Món hàng",
                    quantity=i.quantity,
                    unit_price_vnd=i.unit_price_vnd,
                )
                for i in extraction.receipt_items.items
            ]
            receipt = ReceiptExtension(
                items=items,
                total_vnd=extraction.receipt_items.total_vnd,
                items_sum_vnd=sum(i.quantity * i.unit_price_vnd for i in items),
            )

        if extraction.listing is not None and (
            req.mode == ContentMode.SHOP or extraction.listing.listed_price_vnd is not None
        ):
            prices = (await self._runner.call("lookup_reference_price", ctx)).result
            shop = check_listing(extraction.listing, prices, url_results, cues)
            for floor in shop.floors:
                self._add_floor(ctx, floor, "F4")
            listing = ListingExtension(
                product_category=extraction.listing.product_category,
                product_key=extraction.listing.product_key,
                listed_price_vnd=shop.listed_price_vnd,
                reference_price_vnd=shop.reference_price_vnd,
                discount_percent=shop.discount_percent,
                requires_deposit=shop.safe_payment_tips,
            )

        if extraction.promo_claim is not None:
            promos = (await self._runner.call("lookup_official_promos", ctx)).result
            result = check_promo(extraction.promo_claim, promos, self._sandbox_clock.now(), cues)
            for floor in result.floors:
                self._add_floor(ctx, floor, "F5")
            official = result.official_promo
            promo = PromoExtension(
                brand=extraction.promo_claim.brand,
                promo_code=grounding.ground_string(extraction.promo_claim.promo_code, redacted),
                matched=result.matched,
                official_promo=(
                    OfficialPromo(title_vi=official.title_vi, valid_to=official.valid_to.isoformat())
                    if official is not None
                    else None
                ),
            )

        if receipt is None and listing is None and promo is None:
            return None
        return Extensions(receipt=receipt, listing=listing, promo=promo)

    # ------------------------------------------------------------------ prefill, pending

    def _build_prefill(
        self,
        origin: ContentOrigin,
        ctx: RequestContext,
        accounts: list[_Account],
        extraction: QuarantinedExtraction | None,
        qr: QrVerification | None,
        qr_valid: bool,
        amount: int | None,
        redacted: str,
        linked: Any = None,
    ) -> Prefill | None:
        primary = accounts[0] if accounts else None
        if linked is not None:  # X1: the user's own linked account wins over any account in the content
            primary = _Account(str(linked.bank_bin), linked.account_number)
        if primary is None and not amount:
            return None
        memo = None
        if extraction is not None and extraction.payment_request is not None:
            memo = grounding.ground_string(extraction.payment_request.memo, redacted)
        bank_bin = primary.bank_bin if primary else None
        return Prefill(
            bank_bin=bank_bin,
            bank_name=bank_name(bank_bin) if bank_bin else None,
            account_number=primary.digits if primary else None,
            amount_vnd=amount or None,
            memo=memo,
            account_origin=_ORIGIN_TO_ACCOUNT_ORIGIN[origin],
            source_integrity_for_flow_a=(
                SourceIntegrity.OCR_UNCONFIRMED
                if ctx.source_integrity == SourceIntegrity.OCR_UNCONFIRMED
                else SourceIntegrity.VALID_VIETQR_CRC
                if qr_valid and primary is not None and qr is not None
                else SourceIntegrity.USER_TYPED
            ),
        )

    def _store_pending(
        self,
        ctx: RequestContext,
        account: _Account | None,
        name: NameInquiryResult | None,
        extraction: QuarantinedExtraction | None,
        amount: int | None = None,
        origin: ContentOrigin | None = None,
    ) -> NameConfirmation | None:
        if account is None or account.bank_bin is None or name is None:
            return None
        pending = self._pending.create(
            ctx.session_id,
            account.bank_bin,
            account.digits,
            extraction=extraction,
            floors_snapshot=FloorSet(ctx.floors.floors),
        )
        self._pending.update(
            pending.pending_id,
            extra={"amount_vnd": amount, "origin": origin.value if origin else None},
        )
        return NameConfirmation(
            pending_id=pending.pending_id,
            display_name=name.display_name,
            bank_name=name.bank_name,
            account_digits_spaced=" ".join(account.digits),
            found=name.found,
            sandbox=name.sandbox,
        )

    # ------------------------------------------------------------------ Risk_Memory + audit

    async def _write_risk_memory(
        self,
        ctx: RequestContext,
        composed: ComposedVerdict,
        accounts: list[_Account],
        url_results: list[Any],
    ) -> None:
        hard_codes = {f.reason_code for f in ctx.floors if f.tier == DecisionTier.HARD_HOLD}
        code = next(
            (c for c in ordered_reason_codes(ctx.floors) if c in hard_codes),
            None,
        )
        if code is None:
            return
        for acct in accounts:
            await self._runner.call(
                "risk_memory_write", ctx, key=account_key(acct.bank_bin, acct.digits), reason_code=code
            )
        for domain in dict.fromkeys(u.domain for u in url_results):
            await self._runner.call(
                "risk_memory_write", ctx, key=domain_key(domain), reason_code=code
            )

    def _write_audit(
        self,
        ctx: RequestContext,
        verdict_id: str,
        composed: ComposedVerdict,
        hash_only: bool,
        *,
        original: str | None,
        redacted: str | None,
        extraction: QuarantinedExtraction | None,
        timings: StageTimings,
        extra: dict[str, Any],
    ) -> None:
        verdict = composed.verdict
        forced = bool(ctx.debug and ctx.debug.force_llm_output is not None)
        record: dict[str, Any] = {
            "ts": self._clock.now().isoformat(),
            "audit_id": f"au_{uuid.uuid4().hex[:16]}",
            "request_id": ctx.request_id,
            "verdict_id": verdict_id,
            "channel": ctx.channel,
            "session_hash": ctx.payer_session_hash,
            "llm_provider": "forced" if forced else self._llm.name,
            "decision_tier": ctx.floors.final_tier.name,
            "reason_codes": list(verdict.reason_codes),
            "reason_codes_truncated": list(composed.overflow_reason_codes),
            "rules_fired": [r.model_dump() for r in ctx.rules_fired],
            "stop_codes": [s.value for s in dict.fromkeys(ctx.stop_codes)],
            "trace": [s.model_dump() for s in ctx.trace.steps],
            "reasoning_summary": extraction.reasoning_summary if extraction else None,
            "stage_timings_ms": timings.model_dump(),
            "extra": extra,
        }
        record = apply_consent(
            record,
            explicit_consent_flag=ctx.explicit_consent_flag and not hash_only,
            original=original,
            redacted_text=redacted,
        )
        self._audit.append(record)

    # ------------------------------------------------------------------ OCR confirmation

    async def reevaluate_confirmed(self, session_id: str, pending_id: str) -> FlowBResult | None:
        """Re-run the verdict after the user confirmed the NAPAS name (R2 now satisfied).

        Returns ``None`` when the pending record is unknown or belongs to another session.
        """
        pending = self._pending.get(pending_id, session_id)
        if pending is None:
            return None
        started = time.perf_counter()
        ctx = RequestContext.create(
            session_id, "FLOW_B", self._secret, request_id=f"req_{uuid.uuid4().hex[:16]}"
        )
        ctx.source_integrity = SourceIntegrity.OCR_CONFIRMED_BY_USER
        snapshot = pending.floors_snapshot
        ctx.floors = FloorSet(
            f
            for f in (snapshot.floors if snapshot is not None else ())
            if not (f.rule == "R2" and f.reason_code == mapping.ocr_confirm_floor().reason_code)
        )
        extraction = pending.extraction
        amount = pending.extra.get("amount_vnd")
        try:
            risk = None
            await self._runner.call("risk_memory_lookup", ctx, bank_bin=pending.bin, account=pending.account)
            outcome = await self._runner.call(
                RECIPIENT_RISK_TOOL,
                ctx,
                bank_bin=pending.bin,
                account=pending.account,
                amount_vnd=amount or 0,
            )
            if isinstance(outcome.result, RecipientRisk):
                risk = outcome.result
            total_24h = self._ledger.total_24h(session_id) if self._ledger is not None else 0
            swap = self._policy.before_emit_flow_b(
                ctx, extraction=extraction, amount_vnd=amount, total_24h_vnd=total_24h, risk=risk
            )
            if len(ctx.floors) == 0:
                self._add_floor(ctx, mapping.no_scam_signal_floor(), "BASELINE")
            composed = compose_verdict(
                ctx.floors,
                extraction_playbook=extraction.scam_playbook.value if extraction else None,
                origin_ocr=False,
                account_swap_detected=swap,
            )
        except Exception:  # noqa: BLE001 - never ALLOW on an unexpected failure
            req = FlowBCheckRequest(
                content={"origin": pending.extra.get("origin") or "OCR", "text": "x"}  # type: ignore[arg-type]
            )
            return self._emergency(ctx, req, started)
        tier = ctx.floors.final_tier
        record = self._verdicts.put(
            session_id=session_id,
            channel="FLOW_B",
            tier=tier,
            floors=FloorSet(ctx.floors.floors),
            tx=VerdictTx(bin=pending.bin, account=pending.account, amount=amount),
            extra={"origin": pending.extra.get("origin"), "source_integrity": ctx.source_integrity.value},
        )
        persist = self._policy.before_persist(ctx)
        if tier == DecisionTier.HARD_HOLD:
            await self._write_risk_memory(ctx, composed, [_Account(pending.bin, pending.account)], [])
        total_ms = self._ms(started)
        timings = StageTimings(total=total_ms)
        self._write_audit(
            ctx,
            record.verdict_id,
            composed,
            persist.hash_only,
            original=None,
            redacted=None,
            extraction=extraction,
            timings=timings,
            extra={"origin": pending.extra.get("origin"), "reevaluated": True},
        )
        self._stats.record(session_id, tier)
        self._pending.update(pending_id, status="CONFIRMED")
        prefill = Prefill(
            bank_bin=pending.bin,
            bank_name=bank_name(pending.bin),
            account_number=pending.account,
            amount_vnd=amount or None,
            account_origin=AccountOrigin.OCR,
            source_integrity_for_flow_a=SourceIntegrity.OCR_CONFIRMED_BY_USER,
        )
        cues = list(extraction.manipulation_cues) if extraction else []
        trusted = [TrustedContactRef(name=c.name, phone=c.phone) for c in self._wallet.trusted_contacts()]
        hints = compute_ui_hints(
            tier=tier,
            reason_codes=composed.verdict.reason_codes,
            cues=cues,
            client_time=None,
            prefill=prefill,
            listing_requires_deposit=False,
            trusted_contacts=trusted,
            hotline=self._hotline,
        )
        response = CheckResponse(
            request_id=ctx.request_id,
            verdict_id=record.verdict_id,
            channel="FLOW_B",
            verdict=composed.verdict,
            ui_hints=hints,
            prefill=prefill,
            signals=Signals(
                scam_playbook=extraction.scam_playbook if extraction else None,
                manipulation_cues=cues,
            ),
            sandbox_sources=SANDBOX_SOURCES,
            trace=ctx.trace.steps,
            rules_fired=list(ctx.rules_fired),
            stop_codes=list(dict.fromkeys(ctx.stop_codes)),
            stage_timings_ms=timings,
            latency_ms=total_ms,
        )
        return FlowBResult(response=response, verdict_id=record.verdict_id)

    # ------------------------------------------------------------------ failure path

    def _emergency(self, ctx: RequestContext, req: FlowBCheckRequest, started: float) -> FlowBResult:
        """Unexpected error: SOFT ``RC_LLM_UNAVAILABLE_FALLBACK`` (or higher), never ALLOW."""
        floors = FloorSet(ctx.floors.floors)
        floors.add(mapping.llm_unavailable_floor())
        ctx.floors = floors
        composed = compose_verdict(floors)
        tier = floors.final_tier
        record = self._verdicts.put(
            session_id=ctx.session_id,
            channel="FLOW_B",
            tier=tier,
            floors=FloorSet(floors.floors),
            extra={"origin": req.content.origin.value, "error": True},
        )
        persist = self._policy.before_persist(ctx)
        total_ms = self._ms(started)
        timings = StageTimings(total=total_ms)
        self._write_audit(
            ctx,
            record.verdict_id,
            composed,
            persist.hash_only,
            original=req.content.text or req.content.qr_payload,
            redacted=None,
            extraction=None,
            timings=timings,
            extra={"origin": req.content.origin.value, "error": True},
        )
        self._stats.record(ctx.session_id, tier)
        response = CheckResponse(
            request_id=ctx.request_id,
            verdict_id=record.verdict_id,
            channel="FLOW_B",
            verdict=composed.verdict,
            trace=ctx.trace.steps,
            rules_fired=list(ctx.rules_fired),
            stop_codes=list(dict.fromkeys(ctx.stop_codes)),
            stage_timings_ms=timings,
            latency_ms=total_ms,
        )
        return FlowBResult(response=response, verdict_id=record.verdict_id)

