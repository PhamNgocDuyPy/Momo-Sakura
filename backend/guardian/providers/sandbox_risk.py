"""Sandbox RiskDataProvider backed by fixtures/risk_sandbox.json."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import ValidationError

from guardian.providers.base import NameInquiryResult, PayerHistory, RecipientRisk
from guardian.providers.fixture_loader import FixtureError, load_json
from guardian.tools.banks import bank_name

_FILE = "risk_sandbox.json"


class SandboxRiskProvider:
    def __init__(self, fixtures_dir: Path) -> None:
        raw = load_json(fixtures_dir, _FILE)
        try:
            self._defaults: dict[str, Any] = dict(raw["defaults"])
            self._accounts: dict[tuple[str, str], dict[str, Any]] = {
                (a["bank_bin"], a["account_number"]): a for a in raw["accounts"]
            }
            # Validate eagerly so a corrupt fixture stops startup.
            for acc in self._accounts.values():
                self._risk_of(acc)
            RecipientRisk(**self._risk_kwargs(self._defaults))
        except (KeyError, TypeError, ValidationError) as exc:
            raise FixtureError(f"Thiếu hoặc hỏng fixture: {_FILE}") from exc

    def _risk_kwargs(self, src: dict[str, Any]) -> dict[str, Any]:
        d = self._defaults
        return {
            "simo_hit": src.get("simo_hit", d["simo_hit"]),
            "gnn_mule_score": src.get("gnn_mule_score", d["gnn_mule_score"]),
            "fan_in_senders_per_hour": src.get("fan_in_senders_per_hour", d["fan_in_senders_per_hour"]),
            "account_age_days": src.get("account_age_days", d["account_age_days"]),
        }

    def _risk_of(self, acc: dict[str, Any]) -> RecipientRisk:
        return RecipientRisk(**self._risk_kwargs(acc), found=True)

    async def name_inquiry(self, bank_bin: str, account_number: str) -> NameInquiryResult:
        acc = self._accounts.get((bank_bin, account_number))
        if acc is None:
            return NameInquiryResult(found=False)
        return NameInquiryResult(
            found=True,
            display_name=acc.get("napas_name"),
            bank_name=bank_name(bank_bin),
        )

    async def recipient_risk(self, bank_bin: str, account_number: str, amount_vnd: int) -> RecipientRisk:
        acc = self._accounts.get((bank_bin, account_number))
        if acc is None:
            return RecipientRisk(**self._risk_kwargs({}), found=False)
        return self._risk_of(acc)

    async def payer_history(self, payer_session_hash: str, bank_bin: str, account_number: str) -> PayerHistory:
        # Sandbox history is account-scoped, not session-scoped.
        acc = self._accounts.get((bank_bin, account_number))
        if acc is None:
            return PayerHistory()
        return PayerHistory(
            has_history=bool(acc.get("has_history", self._defaults["has_history"])),
            total_24h_vnd=int(acc.get("total_24h_vnd", self._defaults["total_24h_vnd"])),
        )
