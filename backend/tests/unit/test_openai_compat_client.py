"""OpenAICompatClient over httpx.MockTransport (no real network)."""
from __future__ import annotations

import asyncio
import json
from typing import Any, Callable

import httpx
import pytest

from guardian.config import Settings, validate_startup
from guardian.llm.factory import build_llm
from guardian.llm.openai_compat_client import OpenAICompatClient, build_schema
from guardian.schemas.enums import ContentMode
from guardian.schemas.extraction import FALLBACK_EXTRACTION, QuarantinedExtraction
from guardian.schemas.planner import PlannerIntent
from tests.conftest import make_settings

KEY = "sk-test-SECRET-1234567890"
BASE = "https://llm.example.test/v1"
VALID = FALLBACK_EXTRACTION.model_dump(mode="json")


def settings(**kw: Any) -> Settings:
    base: dict[str, Any] = {
        "llm_provider": "openai_compat",
        "openai_compat_base_url": BASE + "/",
        "openai_compat_api_key": KEY,
        "openai_compat_model": "test-model",
    }
    base.update(kw)
    return make_settings(**base)


def chat(content: str | None = None, finish: str = "stop", **message: Any) -> dict[str, Any]:
    return {"choices": [{"finish_reason": finish, "message": {"role": "assistant", "content": content, **message}}]}


def make_client(
    handler: Callable[[httpx.Request], httpx.Response], **kw: Any
) -> tuple[OpenAICompatClient, list[httpx.Request]]:
    seen: list[httpx.Request] = []

    def wrapped(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return handler(request)

    http = httpx.AsyncClient(transport=httpx.MockTransport(wrapped))
    return OpenAICompatClient(settings(**kw), http_client=http), seen


def reply(body: Any, status: int = 200) -> Callable[[httpx.Request], httpx.Response]:
    return lambda _r: httpx.Response(status, json=body)


def extract(client: OpenAICompatClient, text: str = "hello"):
    return asyncio.run(client.extract(text, ContentMode.GENERAL))


def body_of(request: httpx.Request) -> dict[str, Any]:
    return json.loads(request.content)


def test_json_schema_mode_request_shape_and_ok() -> None:
    client, seen = make_client(reply(chat(json.dumps(VALID))))
    result = extract(client)
    assert result.status == "OK" and result.value == FALLBACK_EXTRACTION
    req = seen[0]
    assert str(req.url) == BASE + "/chat/completions"
    assert req.headers["authorization"] == f"Bearer {KEY}"
    body = body_of(req)
    assert body["model"] == "test-model" and body["max_tokens"] == 280
    rf = body["response_format"]
    assert rf["type"] == "json_schema" and rf["json_schema"]["strict"] is True
    schema = rf["json_schema"]["schema"]
    dumped = json.dumps(schema)
    assert "$ref" not in dumped and "$defs" not in dumped
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == set(schema["properties"])
    assert "tools" not in body


def test_tools_mode() -> None:
    client, seen = make_client(
        reply(chat(None, "tool_calls", tool_calls=[
            {"id": "c1", "type": "function",
             "function": {"name": "emit_quarantined_extraction", "arguments": json.dumps(VALID)}}
        ])),
        openai_compat_json_mode="tools",
    )
    result = extract(client)
    assert result.status == "OK"
    body = body_of(seen[0])
    assert "response_format" not in body
    assert body["tools"][0]["function"]["parameters"]["additionalProperties"] is False
    assert body["tool_choice"] == {"type": "function", "function": {"name": "emit_quarantined_extraction"}}


def test_tools_mode_wrong_function_name() -> None:
    client, _ = make_client(
        reply(chat(None, "tool_calls", tool_calls=[
            {"id": "c1", "type": "function", "function": {"name": "other", "arguments": "{}"}}
        ])),
        openai_compat_json_mode="tools",
    )
    assert extract(client).status == "NO_TOOL_CALL"


def test_json_object_mode_puts_schema_in_system_prompt() -> None:
    client, seen = make_client(reply(chat(json.dumps(VALID))), openai_compat_json_mode="json_object")
    assert extract(client).status == "OK"
    body = body_of(seen[0])
    assert body["response_format"] == {"type": "json_object"}
    system = body["messages"][0]
    assert system["role"] == "system" and "reasoning_summary" in system["content"]


def test_fenced_json_is_parsed() -> None:
    client, _ = make_client(reply(chat("```json\n" + json.dumps(VALID) + "\n```")))
    assert extract(client).status == "OK"


def test_untrusted_wrapping_for_extractor_but_not_planner() -> None:
    client, seen = make_client(reply(chat(json.dumps(VALID))))
    extract(client, "chuyen tien ngay")
    user = body_of(seen[0])["messages"][-1]["content"]
    assert user.startswith("<untrusted_content id=") and "chuyen tien ngay" in user

    planner = {"intent": "UNKNOWN", "confidence_level": "LOW", "transfer": None, "spend": None, "split": None}
    client, seen = make_client(reply(chat(json.dumps(planner))))
    result = asyncio.run(client.plan("chuyển 50k cho mẹ"))
    assert result.status == "OK" and isinstance(result.value, PlannerIntent)
    assert body_of(seen[0])["messages"][-1]["content"] == "chuyển 50k cho mẹ"


def test_invalid_schema_and_no_json() -> None:
    bad = {**VALID, "unexpected": 1}
    assert extract(make_client(reply(chat(json.dumps(bad))))[0]).status == "INVALID_SCHEMA"
    assert extract(make_client(reply(chat("Xin lỗi, tôi không thể.")))[0]).status == "NO_TOOL_CALL"
    assert extract(make_client(reply(chat(None)))[0]).status == "NO_TOOL_CALL"


def test_truncated_and_refusal() -> None:
    assert extract(make_client(reply(chat('{"a":', "length")))[0]).status == "TRUNCATED"
    assert extract(make_client(reply(chat(None, "content_filter")))[0]).status == "REFUSAL"
    assert extract(make_client(reply(chat(None, "stop", refusal="no")))[0]).status == "REFUSAL"


@pytest.mark.parametrize("status", [401, 403, 429, 500, 503])
def test_http_errors_map_to_error_without_leaking(status: int) -> None:
    body = {"error": {"message": f"echo of user text 0912345678 and {KEY}"}}
    result = extract(make_client(reply(body, status))[0])
    assert result.status == "ERROR" and result.raw_stop_reason == f"http_{status}"
    assert KEY not in repr(result) and "0912345678" not in repr(result)


def test_timeout_and_network_errors() -> None:
    def timeout(_r: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout(f"timeout with {KEY}")

    def network(_r: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom")

    r1 = extract(make_client(timeout)[0])
    r2 = extract(make_client(network)[0])
    assert (r1.status, r1.raw_stop_reason) == ("ERROR", "ReadTimeout")
    assert (r2.status, r2.raw_stop_reason) == ("ERROR", "ConnectError")
    assert KEY not in repr(r1)


def test_non_json_200_body_is_error() -> None:
    client, _ = make_client(lambda _r: httpx.Response(200, text="<html>"))
    assert extract(client).status == "ERROR"


def test_timeout_includes_margin() -> None:
    client = OpenAICompatClient(settings(llm_timeout_ms=4000))
    assert client._timeout == 4.5


def test_key_not_in_repr_of_settings_or_client() -> None:
    s = settings()
    assert KEY not in repr(s) and KEY not in str(s)
    assert KEY not in repr(OpenAICompatClient(s))


def test_build_schema_inlines_refs_for_planner() -> None:
    for model in (QuarantinedExtraction, PlannerIntent):
        for strict in (True, False):
            text = json.dumps(build_schema(model, strict=strict))
            assert "$ref" not in text and "$defs" not in text


def test_factory_builds_openai_compat() -> None:
    llm = build_llm(settings())
    assert isinstance(llm, OpenAICompatClient) and llm.name == "openai_compat"


def test_validate_startup_requires_all_vars(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        validate_startup(settings(openai_compat_api_key="", openai_compat_model=""))
    assert exc.value.code == 2
    err = capsys.readouterr().err
    assert "OPENAI_COMPAT_API_KEY" in err and "OPENAI_COMPAT_MODEL" in err and "Thiếu" in err
    with pytest.raises(SystemExit) as exc:
        validate_startup(settings(openai_compat_base_url=""))
    assert exc.value.code == 2
    validate_startup(settings())  # complete config passes
    validate_startup(make_settings())  # mock needs nothing


@pytest.mark.parametrize(
    ("overrides", "provider", "model"),
    [
        ({}, "openai_compat", "test-model"),
        ({"llm_provider": "anthropic", "anthropic_api_key": "k", "anthropic_model": "claude-x"}, "anthropic", "claude-x"),
        ({"llm_provider": "mock"}, "mock", None),
    ],
)
async def test_health_reports_model_without_key(overrides: dict[str, Any], provider: str, model: str | None) -> None:
    from guardian.main import create_app

    transport = httpx.ASGITransport(app=create_app(settings(**overrides)))
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        data = (await c.get("/api/health")).json()
    assert data["llm_provider"] == provider and data["llm_model"] == model
    assert KEY not in json.dumps(data)
