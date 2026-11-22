"""Sandbox WalletDataProvider backed by fixtures/wallet_sandbox.json."""
from __future__ import annotations

from pathlib import Path

from pydantic import ValidationError

from guardian.providers.base import (
    BillRecord,
    Budget,
    Contact,
    Subscription,
    TrustedContact,
    WalletProfile,
    WalletTransaction,
)
from guardian.providers.fixture_loader import FixtureError, load_json

_FILE = "wallet_sandbox.json"


class SandboxWalletProvider:
    def __init__(self, fixtures_dir: Path) -> None:
        raw = load_json(fixtures_dir, _FILE)
        try:
            self._transactions = [WalletTransaction(**t) for t in raw["transactions"]]
            self._contacts = [Contact(**c) for c in raw["contacts"]]
            self._bills = [BillRecord(**b) for b in raw["bills"]]
            self._subscriptions = [Subscription(**s) for s in raw["subscriptions"]]
            self._budgets = [Budget(**b) for b in raw["budgets"]]
            self._trusted = [TrustedContact(**t) for t in raw["trusted_contacts"]]
            self._profile = WalletProfile(**raw["profile"])
        except (KeyError, TypeError, ValidationError) as exc:
            raise FixtureError(f"Thiếu hoặc hỏng fixture: {_FILE}") from exc

    def transactions(self) -> list[WalletTransaction]:
        return list(self._transactions)

    def contacts(self) -> list[Contact]:
        return list(self._contacts)

    def bills(self) -> list[BillRecord]:
        return list(self._bills)

    def subscriptions(self) -> list[Subscription]:
        return list(self._subscriptions)

    def budgets(self) -> list[Budget]:
        return list(self._budgets)

    def trusted_contacts(self) -> list[TrustedContact]:
        return list(self._trusted)

    def profile(self) -> WalletProfile:
        return self._profile
