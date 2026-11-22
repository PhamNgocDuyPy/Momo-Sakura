"""Provider interfaces for data that is infeasible to obtain for real (SIMO, GNN, NAPAS, wallet history)."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

from guardian.schemas.enums import SpendCategory


class _Model(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class NameInquiryResult(_Model):
    found: bool
    display_name: str | None = None
    bank_name: str | None = None
    sandbox: bool = True


class RecipientRisk(_Model):
    simo_hit: bool = False
    gnn_mule_score: float = Field(default=0.05, ge=0.0, le=1.0)
    fan_in_senders_per_hour: int = Field(default=0, ge=0)
    account_age_days: int = Field(default=365, ge=0)
    found: bool = False
    sandbox: bool = True


class PayerHistory(_Model):
    has_history: bool = False
    total_24h_vnd: int = Field(default=0, ge=0)


class WalletTransaction(_Model):
    id: str
    at: datetime
    direction: Literal["IN", "OUT"]
    category: SpendCategory
    counterparty: str
    amount_vnd: int = Field(gt=0)


class Contact(_Model):
    id: str
    display_name: str
    aliases: tuple[str, ...] = ()
    bank_bin: str
    account_number: str


class BillRecord(_Model):
    provider_id: str
    provider_name: str
    period: str  # "YYYY-MM"
    amount_vnd: int = Field(ge=0)
    due_date: date
    status: Literal["PAID", "UNPAID"]


class Subscription(_Model):
    id: str
    name: str
    amount_vnd: int = Field(ge=0)
    renewal_date: date
    last_used_at: datetime | None = None


class Budget(_Model):
    category: SpendCategory
    limit_vnd: int = Field(gt=0)


class TrustedContact(_Model):
    name: str
    phone: str


class WalletProfile(_Model):
    """The user's own receiving account (payee for bill splitting)."""

    display_name: str
    bank_bin: str
    account_number: str


@runtime_checkable
class RiskDataProvider(Protocol):
    async def name_inquiry(self, bank_bin: str, account_number: str) -> NameInquiryResult: ...

    async def recipient_risk(self, bank_bin: str, account_number: str, amount_vnd: int) -> RecipientRisk: ...

    async def payer_history(self, payer_session_hash: str, bank_bin: str, account_number: str) -> PayerHistory: ...


@runtime_checkable
class WalletDataProvider(Protocol):
    def transactions(self) -> list[WalletTransaction]: ...

    def contacts(self) -> list[Contact]: ...

    def bills(self) -> list[BillRecord]: ...

    def subscriptions(self) -> list[Subscription]: ...

    def budgets(self) -> list[Budget]: ...

    def trusted_contacts(self) -> list[TrustedContact]: ...

    def profile(self) -> WalletProfile: ...
