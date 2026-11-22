"""Bedrock provider placeholder (not implemented)."""

from __future__ import annotations

from guardian.llm.base import LLMResult, ProviderNotImplementedError
from guardian.schemas.enums import ContentMode
from guardian.schemas.extraction import QuarantinedExtraction
from guardian.schemas.planner import PlannerIntent

_MESSAGE = "provider chưa được cài đặt"


class BedrockStub:
    name = "bedrock"

    async def extract(self, redacted_text: str, mode: ContentMode) -> LLMResult[QuarantinedExtraction]:
        raise ProviderNotImplementedError(_MESSAGE)

    async def plan(self, tokenized_command: str) -> LLMResult[PlannerIntent]:
        raise ProviderNotImplementedError(_MESSAGE)
