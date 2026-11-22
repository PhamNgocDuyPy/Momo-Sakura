"""fast-unblock, context and transfer commit endpoints."""

from __future__ import annotations

import uuid
import httpx
import pytest

H = {"X-Guardian-Session": str(uuid.uuid4())}
GNN = {"bank_bin": "970407", "account_number": "19033344455501", "amount_vnd": 500000}
SIMO = {"bank_bin": "970422", "account_number": "0909123456", "amount_vnd": 500000}
COLD = {"bank_bin": "970436", "account_number": "5555555555", "amount_vnd": 500000}
UNBLOCK = {"method": "SANDBOX_OTP", "code": "123456"}


async def _check(client: httpx.AsyncClient, body: dict) -> dict:
    r = await client.post("/api/flow-a/check", json=body, headers=H)
    assert r.status_code == 200, r.text
    return r.json()


async def test_fast_unblock_gnn(client: httpx.AsyncClient) -> None:
    first = await _check(client, GNN)
    assert first["verdict"]["allow_fast_unblock"] is True
    r = await client.post(
        "/api/flow-a/fast-unblock",
        json={"verdict_id": first["verdict_id"], "identity_check": UNBLOCK, "purpose": "PAY_RENT"},
        headers=H,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["channel"] == "FAST_UNBLOCK"
    assert body["verdict"]["decision_tier"] == "SOFT_FRICTION"
    assert "RC_FAST_UNBLOCK_VERIFIED" in body["verdict"]["reason_codes"]
    assert body["verdict"]["cooling_off_seconds"] == 30
    assert body["verdict"]["allow_fast_unblock"] is False


async def test_fast_unblock_rejections(client: httpx.AsyncClient) -> None:
    gnn = await _check(client, GNN)
    simo = await _check(client, SIMO)
    bad = await client.post(
        "/api/flow-a/fast-unblock",
        json={
            "verdict_id": gnn["verdict_id"],
            "identity_check": {"method": "SANDBOX_OTP", "code": "000000"},
            "purpose": "OTHER",
        },
        headers=H,
    )
    assert bad.status_code == 400 and bad.json()["error"] == "IDENTITY_CHECK_FAILED"
    no = await client.post(
        "/api/flow-a/fast-unblock",
        json={"verdict_id": simo["verdict_id"], "identity_check": UNBLOCK, "purpose": "OTHER"},
        headers=H,
    )
    assert no.status_code == 409 and no.json()["error"] == "FAST_UNBLOCK_NOT_ALLOWED"


@pytest.mark.parametrize(
    ("context", "tier", "code", "cooling"),
    [
        ("IN_STORE", "ALLOW", "RC_CONTEXT_IN_STORE_DECLARED", 0),
        ("ONLINE_ORDER", "SOFT_FRICTION", "RC_CONTEXT_ONLINE_ORDER_DECLARED", 15),
        ("URGENT_RELATIVE", "SOFT_FRICTION", "RC_CONTEXT_RELATIVE_URGENT_DECLARED", 30),
        ("AUTHORITY_REQUEST", "SOFT_FRICTION", "RC_CONTEXT_AUTHORITY_DECLARED", 60),
    ],
)
async def test_context_branches(
    client: httpx.AsyncClient, context: str, tier: str, code: str, cooling: int
) -> None:
    first = await _check(client, COLD)
    assert "RC_COLD_START_NEEDS_CONTEXT" in first["verdict"]["reason_codes"]
    r = await client.post(
        "/api/flow-a/context",
        json={"verdict_id": first["verdict_id"], "context": context},
        headers=H,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["channel"] == "CONTEXT"
    assert body["verdict"]["decision_tier"] == tier
    assert body["verdict"]["reason_codes"] == [code]
    assert body["verdict"]["cooling_off_seconds"] == cooling
    hints = body["ui_hints"]
    assert hints["show_context_elicitation"] is False
    assert hints["safe_payment_tips"] is (context == "ONLINE_ORDER")
    assert hints["calm_shield"] is (context == "AUTHORITY_REQUEST")
    questions = len(body["verdict"]["system2_check_questions"])
    assert questions == (2 if context in {"URGENT_RELATIVE", "AUTHORITY_REQUEST"} else 0)


async def test_context_not_applicable(client: httpx.AsyncClient) -> None:
    gnn = await _check(client, GNN)
    r = await client.post(
        "/api/flow-a/context",
        json={"verdict_id": gnn["verdict_id"], "context": "IN_STORE"},
        headers=H,
    )
    assert r.status_code == 409 and r.json()["error"] == "CONTEXT_NOT_APPLICABLE"


async def test_commit_rules(client: httpx.AsyncClient) -> None:
    hard = await _check(client, SIMO)
    r = await client.post(
        "/api/transfer/commit",
        json={"verdict_id": hard["verdict_id"], "cooldown_completed": True},
        headers=H,
    )
    assert r.status_code == 403 and r.json()["error"] == "TRANSFER_BLOCKED_HARD_HOLD"

    first = await _check(client, COLD)
    ctx = await client.post(
        "/api/flow-a/context",
        json={"verdict_id": first["verdict_id"], "context": "URGENT_RELATIVE"},
        headers=H,
    )
    vid = ctx.json()["verdict_id"]
    early = await client.post(
        "/api/transfer/commit",
        json={"verdict_id": vid, "cooldown_completed": True, "answered_questions": 2},
        headers=H,
    )
    assert early.status_code == 409 and early.json()["error"] == "COOLDOWN_NOT_FINISHED"


async def test_commit_success_after_cooldown(client: httpx.AsyncClient) -> None:
    app = client._transport.app  # type: ignore[attr-defined]
    container = app.state.container
    first = await _check(client, COLD)
    vid = first["verdict_id"]  # SOFT cold start, cooling 0, no questions
    ok = await client.post(
        "/api/transfer/commit",
        json={"verdict_id": vid, "cooldown_completed": True},
        headers=H,
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["status"] == "SIMULATED_SENT"
    assert ok.json()["ledger_total_24h_vnd"] >= COLD["amount_vnd"]
    assert container.verdict_store.get(vid, H["X-Guardian-Session"]).cooldown_completed
