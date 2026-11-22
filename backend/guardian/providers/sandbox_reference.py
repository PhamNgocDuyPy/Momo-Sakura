"""Sandbox reference data (official promos, reference prices). Only `providers/` reads `fixtures/`."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from guardian.providers.fixture_loader import FixtureError, load_json

_PROMOS_FILE = "official_promos.json"
_PRICES_FILE = "reference_prices.json"


@runtime_checkable
class ReferenceDataProvider(Protocol):
    def official_promo_rows(self) -> list[dict[str, Any]]: ...

    def reference_price_rows(self) -> list[dict[str, Any]]: ...


class SandboxReferenceProvider:
    def __init__(self, fixtures_dir: Path) -> None:
        promos = load_json(fixtures_dir, _PROMOS_FILE)
        prices = load_json(fixtures_dir, _PRICES_FILE)
        if not isinstance(promos, list) or not isinstance(prices, list):
            raise FixtureError(f"Thiếu hoặc hỏng fixture: {_PROMOS_FILE} / {_PRICES_FILE}")
        self._promos: list[dict[str, Any]] = [dict(r) for r in promos]
        self._prices: list[dict[str, Any]] = [dict(r) for r in prices]

    def official_promo_rows(self) -> list[dict[str, Any]]:
        return [dict(r) for r in self._promos]

    def reference_price_rows(self) -> list[dict[str, Any]]:
        return [dict(r) for r in self._prices]
