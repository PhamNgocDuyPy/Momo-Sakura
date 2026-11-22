"""Select the LLMClient from ``Settings.llm_provider``."""

from __future__ import annotations

from guardian.config import Settings
from guardian.llm.base import LLMClient, ProviderNotImplementedError
from guardian.llm.bedrock_stub import BedrockStub
from guardian.llm.mock import MockLLM


def build_llm(settings: Settings) -> LLMClient:
    provider = settings.llm_provider
    if provider == "mock":
        return MockLLM(delay_ms=settings.mock_llm_delay_ms)
    if provider == "bedrock":
        return BedrockStub()
    if provider == "anthropic":
        try:  # imported lazily: the SDK client is only needed for this provider
            from guardian.llm.anthropic_client import AnthropicClient
        except ModuleNotFoundError as exc:
            raise ProviderNotImplementedError("provider chưa được cài đặt") from exc
        return AnthropicClient(settings)
    if provider == "openai_compat":
        from guardian.llm.openai_compat_client import OpenAICompatClient

        return OpenAICompatClient(settings)
    raise ProviderNotImplementedError(f"unknown LLM_PROVIDER: {provider}")
