from __future__ import annotations

from collections.abc import AsyncIterator

import httpx
import pytest
from hypothesis import HealthCheck, settings as hyp_settings

from guardian.config import Settings
from guardian.main import create_app

hyp_settings.register_profile(
    "ci",
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow],
)
hyp_settings.load_profile("ci")


def make_settings(**overrides: object) -> Settings:
    base: dict[str, object] = {"llm_provider": "mock", "guardian_debug": False}
    base.update(overrides)
    return Settings(_env_file=None, **base)  # type: ignore[arg-type]


@pytest.fixture
def settings() -> Settings:
    return make_settings()


@pytest.fixture
def debug_settings() -> Settings:
    return make_settings(guardian_debug=True)


@pytest.fixture
async def client(settings: Settings) -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=create_app(settings))
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture
async def debug_client(debug_settings: Settings) -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=create_app(debug_settings))
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
