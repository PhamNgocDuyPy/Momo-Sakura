"""MockLLM: deterministic stand-in for a real LLM (no randomness, no clock)."""

from __future__ import annotations

import asyncio

from pydantic import ValidationError

from guardian.llm.base import LLMResult
from guardian.llm.mock_rules import mock_extract, mock_plan
from guardian.schemas.enums import ContentMode
from guardian.schemas.extraction import QuarantinedExtraction
from guardian.schemas.planner import PlannerIntent


class MockLLM:
    name = "mock"

    def __init__(self, delay_ms: int = 0) -> None:
        self._delay_ms = max(0, delay_ms)

    async def _wait(self, delay_ms: int | None) -> int:
        delay = self._delay_ms if delay_ms is None else max(0, delay_ms)
        if delay:
            await asyncio.sleep(delay / 1000)
        return delay  # reported latency equals the simulated delay, so results are reproducible

    async def extract(
        self, redacted_text: str, mode: ContentMode, *, delay_ms: int | None = None
    ) -> LLMResult[QuarantinedExtraction]:
        latency = await self._wait(delay_ms)
        try:
            value = mock_extract(redacted_text, mode)
        except ValidationError:
            return LLMResult(None, "INVALID_SCHEMA", "mock", latency)
        return LLMResult(value, "OK", "mock", latency)

    async def plan(self, tokenized_command: str, *, delay_ms: int | None = None) -> LLMResult[PlannerIntent]:
        latency = await self._wait(delay_ms)
        try:
            value = mock_plan(tokenized_command)
        except ValidationError:
            return LLMResult(None, "INVALID_SCHEMA", "mock", latency)
        return LLMResult(value, "OK", "mock", latency)
