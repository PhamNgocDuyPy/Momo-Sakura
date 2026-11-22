"""F2 (assistant transfer commands), F4 (shop) and F5 (promo) scenarios A03-A05, A08-A10."""

from __future__ import annotations

import uuid
from typing import Any

import httpx
import pytest

from eval.scenario_loader import Scenario, load_scenarios
from guardian.features.contacts import match
from guardian.llm.base import LLMResult
from guardian.main import create_app
from guardian.providers.base import Contact
from guardian.schemas.api_models import AssistantCommandResponse
from tests.scenarios.runner import make_settings, run_scenario

IDS = ["A03", "A04", "A05", "A08", "A09", "A10"]
SCENARIOS: dict[str, Scenario] = {s.id: s for s in load_scenarios() if s.id in IDS}
HEADERS = {"X-Guardian-Session": str(uuid.uuid4())}


def _contact(cid: str, name: str, aliases: tuple[str, ...] = ()) -> Contact:
    return Contact(id=cid, display_name=name, aliases=aliases, bank_bin="970436", account_number="0123456789")


CONTACTS = [
    _contact("minh", "Nguyễn Văn Minh"),
    _contact("lan1", "Trần Thị Lan"),
    _contact("lan2", "Phạm Ngọc Lan"),
    _contact("me", "Mẹ", ("má", "mẹ yêu")),
    _contact("duc", "Đỗ Đức Anh"),
]


def test_fixtures_present() -> None:
    assert sorted(SCENARIOS) == IDS


@pytest.mark.parametrize("scenario_id", IDS)
async def test_scenario(scenario_id: str) -> None:
    result = await run_scenario(SCENARIOS[scenario_id])
    problems = [(c.endpoint, c.status_code, c.mismatches) for c in result.cases if not c.passed]
    assert not problems, problems


# --------------------------------------------------------------------------- contacts.match


@pytest.mark.parametrize(
    ("query", "status", "ids"),
    [
        ("Minh", "RESOLVED", ["minh"]),
        ("minh", "RESOLVED", ["minh"]),
        ("Nguyễn Văn Minh", "RESOLVED", ["minh"]),
        ("nguyen van minh", "RESOLVED", ["minh"]),
        ("Văn Minh", "RESOLVED", ["minh"]),
        ("Thị Lan", "RESOLVED", ["lan1"]),
        ("Lan", "AMBIGUOUS", ["lan1", "lan2"]),
        ("má", "RESOLVED", ["me"]),
        ("ma", "RESOLVED", ["me"]),
        ("Mẹ yêu", "RESOLVED", ["me"]),
        ("Đức", "RESOLVED", ["duc"]),
        ("duc anh", "RESOLVED", ["duc"]),
        ("Hùng", "NOT_FOUND", []),
        ("Minh Lan", "NOT_FOUND", []),  # not a consecutive run in any name
        ("Nguyen Van", "RESOLVED", ["minh"]),
        ("", "NOT_FOUND", []),
        ("  ,  ", "NOT_FOUND", []),
    ],
)
def test_contact_match(query: str, status: str, ids: list[str]) -> None:
    found = match(query, CONTACTS)
    assert found.status == status
    assert [c.id for c in found.candidates] == ids
    assert (found.contact.id if found.contact else None) == (ids[0] if status == "RESOLVED" else None)


# --------------------------------------------------------------------------- assistant service


async def _command(app: Any, text: str) -> httpx.Response:
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        return await client.post("/api/assistant/command", json={"text": text}, headers=HEADERS)


async def test_planner_sees_tokenized_text_and_slots_are_reversed() -> None:
    app = create_app(make_settings())
    llm = app.state.container.llm
    seen: list[str] = []
    original = llm.plan

    async def spy(tokenized: str, *args: Any, **kwargs: Any) -> Any:
        seen.append(tokenized)
        return await original(tokenized, *args, **kwargs)

    llm.plan = spy
    resp = await _command(app, "chuyển 200k cho Minh, sdt 0912345678")
    assert resp.status_code == 200
    assert len(seen) == 1
    assert "Minh" not in seen[0] and "0912345678" not in seen[0]
    body = AssistantCommandResponse.model_validate(resp.json())
    assert body.intent.transfer is not None and body.intent.transfer.recipient_name == "Minh"
    redact = next(s for s in body.trace if s.name == "redact_pii_local")
    assert redact.detail == {"redacted": {"TEN": 1, "SDT": 1}}


async def test_stub_provider_falls_back_to_mock_rules() -> None:
    app = create_app(make_settings(llm_provider="bedrock"))
    resp = await _command(app, "chuyển 200k cho Minh tiền cà phê")
    body = resp.json()
    assert body["result"]["status"] == "RESOLVED"
    fallback = next(s for s in body["trace"] if s["name"] == "plan_fallback")
    assert fallback["detail"]["fallback"] == "mock_rules"


async def test_invalid_planner_output_asks_to_rephrase() -> None:
    app = create_app(make_settings())

    async def bad(_tokenized: str, *args: Any, **kwargs: Any) -> Any:
        return LLMResult(None, "INVALID_SCHEMA", "mock", 0)

    app.state.container.llm.plan = bad
    body = (await _command(app, "chuyển 200k cho Minh")).json()
    assert body["intent"]["intent"] == "UNKNOWN"
    assert body["result"]["type"] == "REPHRASE"
    assert body["result"]["examples_vi"]


@pytest.mark.parametrize(
    ("text", "mode"),
    [
        ("chia hóa đơn lẩu cho 3 người", "SPLIT_BILL"),
        ("tôi muốn mua iphone ở shop này", "SHOP"),
        ("voucher này có thật không", "PROMO"),
        ("kiểm tra giúp tôi tin nhắn này", "GENERAL"),
    ],
)
async def test_open_mode_routing(text: str, mode: str) -> None:
    body = (await _command(create_app(make_settings()), text)).json()
    assert body["result"]["type"] == "OPEN_MODE"
    assert body["result"]["mode"] == mode


async def test_unknown_and_missing_recipient_rephrase() -> None:
    app = create_app(make_settings())
    assert (await _command(app, "hôm nay trời đẹp quá")).json()["result"]["type"] == "REPHRASE"
    assert (await _command(app, "chuyển 200k")).json()["result"]["type"] == "REPHRASE"


async def test_command_length_limit_and_session_required() -> None:
    app = create_app(make_settings())
    assert (await _command(app, "a" * 201)).status_code == 422
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        assert (await client.post("/api/assistant/command", json={"text": "xin chào"})).status_code == 400


async def test_pasted_word_plan_is_not_a_hijack() -> None:
    """``plan`` joined the tool allowlist for the Planner call; the English word must stay harmless."""
    app = create_app(make_settings())
    body = {"content": {"origin": "PASTE", "text": "Let's plan lunch tomorrow at noon"}}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/flow-b/check?stream=false", json=body, headers=HEADERS)
    assert resp.json()["verdict"]["decision_tier"] == "ALLOW"
