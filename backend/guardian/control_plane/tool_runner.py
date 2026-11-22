"""ToolRunner: the only path through which the control plane invokes tools.

LLMs never call this module. Callers are FlowAGate, FlowBOrchestrator,
AssistantService and ``features/`` modules.
"""

from __future__ import annotations

import inspect
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, Protocol

from guardian.control_plane.session import RequestContext
from guardian.schemas.enums import StopCode
from guardian.schemas.trace import TraceKind

ALLOWED_TOOLS: frozenset[str] = frozenset(
    {
        "verify_vietqr_emvco",
        "check_urls",
        "prompt_guard_cpu_score",
        "redact_pii_local",
        "scan_entities",
        "detect_hijack",
        "napas_name_inquiry_readonly",
        "lookup_recipient_risk_and_simo",
        "lookup_payer_history",
        "risk_memory_lookup",
        "risk_memory_write",
        "quarantined_extract",
        "lookup_official_promos",
        "lookup_reference_price",
        "plan",
    }
)

_LLM_TOOLS: frozenset[str] = frozenset({"quarantined_extract", "plan"})


class ToolNotAllowed(Exception):
    """Raised when a tool name is not in ``ALLOWED_TOOLS``."""

    def __init__(self, name: str) -> None:
        super().__init__(f"tool not allowed: {name}")
        self.name = name


@dataclass(frozen=True)
class Allow:
    """``before_call`` decision: proceed with the tool."""


@dataclass(frozen=True)
class Abort:
    """``before_call`` decision: do not run the tool."""

    stop_code: StopCode
    result_code: str


@dataclass(frozen=True)
class ToolOutcome:
    name: str
    aborted: bool
    result: Any = None
    result_code: str | None = None
    stop_code: StopCode | None = None
    duration_ms: int = 0


class PolicyHooks(Protocol):
    def before_call(self, name: str, args: Mapping[str, Any], ctx: RequestContext) -> Allow | Abort: ...

    def after_call(self, name: str, result: Any, ctx: RequestContext) -> None: ...


ToolFn = Callable[..., Any]


class ToolRunner:
    def __init__(self, tools: Mapping[str, ToolFn], policy: PolicyHooks | None = None) -> None:
        unknown = set(tools) - ALLOWED_TOOLS
        if unknown:
            raise ValueError(f"tools outside allowlist: {sorted(unknown)}")
        self._tools = dict(tools)
        self._policy = policy

    @staticmethod
    def _kind(name: str) -> TraceKind:
        return "llm" if name in _LLM_TOOLS else "tool"

    async def call(self, name: str, ctx: RequestContext, **args: Any) -> ToolOutcome:
        kind = self._kind(name)
        if name not in ALLOWED_TOOLS:
            ctx.trace.record("tool", name, "denied", {"reason": "NOT_ALLOWLISTED"})
            raise ToolNotAllowed(name)

        if self._policy is not None:
            decision = self._policy.before_call(name, args, ctx)
            if isinstance(decision, Abort):
                ctx.stop_codes.append(decision.stop_code)
                ctx.trace.record(kind, name, "aborted", {"result": decision.result_code})
                return ToolOutcome(
                    name=name,
                    aborted=True,
                    result_code=decision.result_code,
                    stop_code=decision.stop_code,
                )

        fn = self._tools.get(name)
        if fn is None:
            ctx.trace.record(kind, name, "error", {"reason": "NOT_REGISTERED"})
            raise LookupError(f"tool not registered: {name}")

        start = ctx.trace.elapsed_ms()
        try:
            result = fn(ctx, **args)
            if inspect.isawaitable(result):
                result = await result
        except Exception as exc:
            ctx.trace.record(
                kind,
                name,
                "error",
                {"error": type(exc).__name__},
                t_start_ms=start,
                duration_ms=ctx.trace.elapsed_ms() - start,
            )
            raise
        duration = ctx.trace.elapsed_ms() - start
        ctx.trace.record(kind, name, "ok", t_start_ms=start, duration_ms=duration)

        if self._policy is not None:
            self._policy.after_call(name, result, ctx)
        return ToolOutcome(name=name, aborted=False, result=result, duration_ms=duration)
