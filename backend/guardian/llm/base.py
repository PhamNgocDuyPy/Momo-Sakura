"""LLMClient protocol and result envelope.

The LLM never calls tools. Control Plane code treats any status other than ``OK`` as a
failure and substitutes a fallback (design.md, LLM_Client).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, Literal, Protocol, TypeVar

from guardian.schemas.enums import ContentMode
from guardian.schemas.extraction import QuarantinedExtraction
from guardian.schemas.planner import PlannerIntent

T = TypeVar("T")

LLMStatus = Literal[
    "OK",
    "INVALID_SCHEMA",
    "REFUSAL",
    "TRUNCATED",
    "NO_TOOL_CALL",
    "ERROR",
    "NOT_IMPLEMENTED",
]


class ProviderNotImplementedError(RuntimeError):
    """Raised by providers that exist only as stubs (e.g. Bedrock)."""


@dataclass(frozen=True)
class LLMResult(Generic[T]):
    value: T | None  # None when the schema is invalid, or on refusal / truncation / error
    status: LLMStatus
    raw_stop_reason: str | None
    latency_ms: int


class LLMClient(Protocol):
    name: str  # "mock" | "anthropic" | "bedrock"

    async def extract(self, redacted_text: str, mode: ContentMode) -> LLMResult[QuarantinedExtraction]: ...

    async def plan(self, tokenized_command: str) -> LLMResult[PlannerIntent]: ...
