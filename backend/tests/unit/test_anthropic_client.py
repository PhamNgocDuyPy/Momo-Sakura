"""AnthropicClient with a fake SDK (no network)."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any

import pytest

from guardian.llm.anthropic_client import EXTRACTION_TOOL, PLANNER_TOOL, AnthropicClient, wrap_untrusted
from guardian.llm.factory import build_llm
from guardian.schemas.enums import ContentMode
from guardian.schemas.extraction import FALLBACK_EXTRACTION
from tests.conftest import make_settings


class FakeMessages:
    def __init__(self, response: Any = None, exc: Exception | None = None) -> None:
        self.response, self.exc, self.kwargs = response, exc, None

    async def create(self, **kwargs: Any) -> Any:
        self.kwargs = kwargs
        if self.exc:
            raise self.exc
        return self.response


def make_client(response: Any = None, exc: Exception | None = None) -> tuple[AnthropicClient, FakeMessages]:
    messages = FakeMessages(response, exc)
    sdk = SimpleNamespace(messages=messages)
    return AnthropicClient(make_settings(llm_provider="anthropic", anthropic_api_key="k"), sdk_client=sdk), messages


def tool_resp(payload: dict[str, Any], name: str = EXTRACTION_TOOL, stop: str = "tool_use") -> Any:
    block = SimpleNamespace(type="tool_use", name=name, input=payload)
    return SimpleNamespace(stop_reason=stop, content=[block])


def run_extract(client: AnthropicClient):
    return asyncio.run(client.extract("hello", ContentMode.GENERAL))


def test_ok_and_request_parameters() -> None:
    client, messages = make_client(tool_resp(FALLBACK_EXTRACTION.model_dump(mode="json")))
    result = run_extract(client)
    assert result.status == "OK" and result.value == FALLBACK_EXTRACTION
    kw = messages.kwargs
    assert kw["max_tokens"] == 280
    assert kw["tool_choice"] == {"type": "tool", "name": EXTRACTION_TOOL}
    assert "temperature" not in kw and "top_p" not in kw
    assert kw["tools"][0]["input_schema"]["additionalProperties"] is False


def test_invalid_schema() -> None:
    payload = {**FALLBACK_EXTRACTION.model_dump(mode="json"), "unexpected": 1}
    assert run_extract(make_client(tool_resp(payload))[0]).status == "INVALID_SCHEMA"


@pytest.mark.parametrize(
    ("stop", "status"),
    [("refusal", "REFUSAL"), ("max_tokens", "TRUNCATED"), ("end_turn", "NO_TOOL_CALL"), ("pause_turn", "NO_TOOL_CALL")],
)
def test_stop_reason_mapping(stop: str, status: str) -> None:
    result = run_extract(make_client(SimpleNamespace(stop_reason=stop, content=[]))[0])
    assert result.status == status and result.value is None and result.raw_stop_reason == stop


def test_wrong_tool_name_is_no_tool_call() -> None:
    resp = tool_resp(FALLBACK_EXTRACTION.model_dump(mode="json"), name="other")
    assert run_extract(make_client(resp)[0]).status == "NO_TOOL_CALL"


def test_sdk_exception_is_error() -> None:
    assert run_extract(make_client(exc=RuntimeError("boom"))[0]).status == "ERROR"


def test_plan_uses_planner_tool_and_maps_invalid() -> None:
    client, messages = make_client(tool_resp({"intent": "BOGUS"}, name=PLANNER_TOOL))
    result = asyncio.run(client.plan("chuyen 2 lit"))
    assert result.status == "INVALID_SCHEMA"
    assert messages.kwargs["tool_choice"]["name"] == PLANNER_TOOL


def test_wrap_untrusted_strips_boundary() -> None:
    wrapped = wrap_untrusted("a abc123 b", boundary="abc123")
    assert wrapped.count("abc123") == 2 and "a  b" in wrapped


def test_factory_builds_anthropic_with_sdk_timeout() -> None:
    llm = build_llm(make_settings(llm_provider="anthropic", anthropic_api_key="k", llm_timeout_ms=4000))
    assert llm.name == "anthropic"
    assert llm._client.timeout == 4.5
