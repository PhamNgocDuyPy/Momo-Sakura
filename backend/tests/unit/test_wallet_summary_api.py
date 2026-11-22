from __future__ import annotations

import uuid

import httpx
import pytest

from guardian.config import Settings
from guardian.main import create_app
from guardian.features.wallet_summary import budget_status
from guardian.schemas.enums import DecisionTier
from guardian.stores.shield_stats import ShieldStats


def test_budget_status_boundaries() -> None:
    assert budget_status(2_550_000, 3_000_000) == (85, "WARNING")
    assert budget_status(79, 100) == (79, "OK")
    assert budget_status(80, 100) == (80, "WARNING")
    assert budget_status(100, 100) == (100, "OVER")


def test_shield_stats_counts_per_session() -> None:
    s = ShieldStats()
    s.record("a", DecisionTier.ALLOW)
    s.record("a", DecisionTier.HARD_HOLD)
    assert s.get("a") == {"checks": 2, "ALLOW": 1, "SOFT_FRICTION": 0, "HARD_HOLD": 1}
    assert s.get("b")["checks"] == 0


@pytest.mark.asyncio
async def test_summary_endpoint() -> None:
    app = create_app(Settings())
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as c:
        r = await c.get("/api/wallet/summary")
        assert r.status_code == 400
        r = await c.get("/api/wallet/summary", headers={"X-Guardian-Session": str(uuid.uuid4())})
    assert r.status_code == 200
    body = r.json()
    assert body["month"] == "2026-11" and body["sandbox"] is True
    assert len(body["recent_transactions"]) == 10
    assert [(a["type"], a.get("provider_id") or a["subscription_id"]) for a in body["alerts"]] == [
        ("BILL_SPIKE", "EVN_HCMC"),
        ("RENEWAL_SOON", "sub_netflix"),
        ("UNUSED_SUBSCRIPTION", "sub_spotify"),
    ]
    assert body["alerts"][0]["increase_percent"] == 40
    assert body["shield_stats"]["checks"] == 0
