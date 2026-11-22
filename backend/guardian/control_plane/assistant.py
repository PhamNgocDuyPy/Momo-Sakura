"""AssistantService (F2/F6 routing): Trusted_Command -> tokenize PII -> Planner -> route.

Only text the user typed into the command box reaches this service (never pasted, OCR or QR
content). PII is replaced by reversible tokens before the Planner sees the text; R1 egress runs
in ``before_call``; the Planner can only return a ``PlannerIntent``. All user-visible strings
come from ``policy/templates_vi.py`` filled with ``format_vnd`` and contact ``display_name``.
When the provider is a stub or unavailable the Mock Planner rules answer instead
(``detail.fallback = "mock_rules"``).
"""

from __future__ import annotations

from typing import Any

from guardian.control_plane.session import RequestContext
from guardian.control_plane.tool_runner import ToolRunner
from guardian.features import contacts as contact_matcher
from guardian.features.spend_query import compute as compute_spend
from guardian.llm.base import LLMClient
from guardian.llm.circuit_breaker import CircuitBreaker
from guardian.llm.mock_rules import mock_plan
from guardian.policy import templates_vi as tv
from guardian.policy.engine import PolicyEngine
from guardian.providers.base import Contact, WalletDataProvider
from guardian.providers.clock import Clock
from guardian.schemas.api_models import (
    AssistantCommandResponse,
    OpenModeResult,
    Prefill,
    RephraseResult,
    ResolvedContact,
    TransferResolutionResult,
)
from guardian.schemas.enums import Confidence, ContentMode, Intent, SourceIntegrity
from guardian.schemas.planner import PlannerIntent, TransferSlots
from guardian.tools.amount import format_vnd
from guardian.tools.banks import bank_name
from guardian.tools.pii import Tokenizer, contact_name_variants

DEFAULT_LLM_TIMEOUT_MS = 4000

_OPEN_MODE: dict[Intent, ContentMode] = {
    Intent.SPLIT_BILL: ContentMode.SPLIT_BILL,
    Intent.SHOP_CHECK: ContentMode.SHOP,
    Intent.CHECK_PROMO: ContentMode.PROMO,
    Intent.CHECK_CONTENT: ContentMode.GENERAL,
}
# Breaker/LLM statuses that mean "provider unavailable": the Mock Planner rules take over.
_UNAVAILABLE = frozenset({"TIMEOUT", "ERROR", "SKIPPED"})


def _resolved(contact: Contact) -> ResolvedContact:
    return ResolvedContact(
        id=contact.id,
        display_name=contact.display_name,
        bank_bin=contact.bank_bin,
        account_number=contact.account_number,
    )


class AssistantService:
    def __init__(
        self,
        *,
        llm: LLMClient,
        wallet_provider: WalletDataProvider,
        policy: PolicyEngine,
        sandbox_clock: Clock,
        session_secret: str,
        llm_timeout_ms: int = DEFAULT_LLM_TIMEOUT_MS,
        breaker: CircuitBreaker | None = None,
    ) -> None:
        self._llm = llm
        self._wallet = wallet_provider
        self._clock = sandbox_clock
        self._secret = session_secret
        self._breaker = breaker or CircuitBreaker(timeout_ms=llm_timeout_ms)
        self._runner = ToolRunner(
            {"redact_pii_local": self._t_redact, "plan": self._t_plan},
            policy,
        )

    # ------------------------------------------------------------------ tools

    @staticmethod
    def _t_redact(
        _ctx: RequestContext, *, text: str, contact_names: tuple[str, ...], tokenizer: Tokenizer
    ) -> tuple[str, dict[str, int]]:
        return tokenizer.redact(text, contact_names)

    async def _t_plan(self, _ctx: RequestContext, *, tokenized_command: str) -> Any:
        return await self._breaker.call(lambda: self._llm.plan(tokenized_command))

    # ------------------------------------------------------------------ entry point

    async def command(self, session_id: str, text: str) -> AssistantCommandResponse:
        ctx = RequestContext.create(session_id, "ASSISTANT", self._secret)
        tokenizer = Tokenizer()
        names = contact_name_variants(self._wallet.contacts())
        tokenized, counts = (
            await self._runner.call(
                "redact_pii_local", ctx, text=text, contact_names=names, tokenizer=tokenizer
            )
        ).result
        for step in reversed(ctx.trace.steps):  # trace shows counts only, never values
            if step.name == "redact_pii_local" and step.status == "ok":
                step.detail = {"redacted": {str(k): int(v) for k, v in counts.items()}}
                break

        intent = await self._plan(ctx, tokenized)
        intent = self._reverse_slots(intent, tokenizer)
        result = self._route(intent)
        return AssistantCommandResponse(intent=intent, result=result, trace=ctx.trace.steps)

    # ------------------------------------------------------------------ planner

    async def _plan(self, ctx: RequestContext, tokenized: str) -> PlannerIntent:
        unknown = PlannerIntent(intent=Intent.UNKNOWN, confidence_level=Confidence.LOW)
        outcome = await self._runner.call("plan", ctx, tokenized_command=tokenized)
        if outcome.aborted:  # R1 egress blocked the Planner call
            return unknown
        breaker = outcome.result
        inner = getattr(breaker, "result", None)
        inner_status = getattr(inner, "status", None)
        value = getattr(inner, "value", None)
        if breaker.status == "OK" and inner_status == "OK" and isinstance(value, PlannerIntent):
            return value
        cause = inner_status if breaker.status == "OK" else breaker.status
        if breaker.status in _UNAVAILABLE or cause == "NOT_IMPLEMENTED":
            ctx.trace.record("stage", "plan_fallback", "ok", {"fallback": "mock_rules", "cause": str(cause)})
            try:
                return mock_plan(tokenized)
            except Exception:  # noqa: BLE001 - never fail the request on a rules error
                return unknown
        ctx.trace.record("stage", "plan_fallback", "ok", {"fallback": "none", "cause": str(cause)})
        return unknown  # INVALID_SCHEMA / REFUSAL / TRUNCATED / NO_TOOL_CALL (Req 14.5)

    @staticmethod
    def _reverse_slots(intent: PlannerIntent, tokenizer: Tokenizer) -> PlannerIntent:
        slots = intent.transfer
        if slots is None:
            return intent
        name = tokenizer.reverse(slots.recipient_name)[:40] if slots.recipient_name else None
        memo = tokenizer.reverse(slots.memo)[:60] if slots.memo else None
        return intent.model_copy(
            update={"transfer": TransferSlots(recipient_name=name, amount_vnd=slots.amount_vnd, memo=memo)}
        )

    # ------------------------------------------------------------------ routing

    def _route(self, intent: PlannerIntent) -> Any:
        if intent.intent == Intent.TRANSFER and intent.transfer is not None:
            return self._route_transfer(intent.transfer)
        if intent.intent == Intent.SPEND_QUERY and intent.spend is not None:
            return compute_spend(self._wallet.transactions(), intent.spend, self._clock.now())
        mode = _OPEN_MODE.get(intent.intent)
        if mode is not None:
            return OpenModeResult(mode=mode, message_vi=tv.F2_OPEN_MODE[mode.value])
        return self._rephrase()

    @staticmethod
    def _rephrase() -> RephraseResult:
        return RephraseResult(message_vi=tv.F2_REPHRASE, examples_vi=list(tv.F2_REPHRASE_EXAMPLES))

    def _route_transfer(self, slots: TransferSlots) -> Any:
        query = (slots.recipient_name or "").strip()
        if not query:
            return self._rephrase()
        amount = slots.amount_vnd
        found = contact_matcher.match(query, self._wallet.contacts())
        candidates = [_resolved(c) for c in found.candidates] if found.status == "AMBIGUOUS" else []
        contact = found.contact

        def prefill(bank_bin: str | None = None, account: str | None = None) -> Prefill:
            return Prefill(
                bank_bin=bank_bin,
                bank_name=bank_name(bank_bin) if bank_bin else None,
                account_number=account,
                amount_vnd=amount,
                memo=slots.memo,
                source_integrity_for_flow_a=SourceIntegrity.USER_TYPED,
            )

        if not amount:  # missing amount is asked first, but the match result is still returned
            name = contact.display_name if contact else query
            return TransferResolutionResult(
                status="NEEDS_AMOUNT",
                contact=_resolved(contact) if contact else None,
                candidates=candidates,
                prefill=prefill(contact.bank_bin, contact.account_number) if contact else None,
                message_vi=tv.F2_NEEDS_AMOUNT.format(name=name),
            )
        if contact is not None:
            return TransferResolutionResult(
                status="RESOLVED",
                contact=_resolved(contact),
                prefill=prefill(contact.bank_bin, contact.account_number),
                message_vi=tv.F2_RESOLVED.format(amount=format_vnd(amount), name=contact.display_name),
            )
        if found.status == "AMBIGUOUS":
            return TransferResolutionResult(
                status="AMBIGUOUS",
                candidates=candidates,
                prefill=prefill(),
                message_vi=tv.F2_AMBIGUOUS.format(count=len(candidates), query=query),
            )
        return TransferResolutionResult(
            status="NOT_FOUND", message_vi=tv.F2_NOT_FOUND.format(query=query)
        )
