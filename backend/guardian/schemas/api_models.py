"""Request/response envelopes for every API endpoint (design.md, API contracts).

All models reject unknown keys. Amounts are integer VND. User-visible strings come from templates.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import ConfigDict, Field

from guardian.schemas.base import ApiModel
from guardian.schemas.enums import (
    AccountOrigin,
    ContentMode,
    ContentOrigin,
    Cue,
    DecisionTierName,
    ProductCategory,
    PromoBrand,
    QrFlag,
    QrResult,
    ScamPlaybook,
    SourceIntegrity,
    SpendCategory,
    SpendMetric,
    SpendPeriod,
    StopCode,
)
from guardian.schemas.planner import PlannerIntent
from guardian.schemas.trace import RuleFiring, TraceStep
from guardian.schemas.verdict import GuardianVerdict

Channel = Literal["FLOW_A", "FLOW_B", "FAST_UNBLOCK", "CONTEXT", "NAME_CONFIRM", "ASSISTANT"]

BankBin = Annotated[str, Field(pattern=r"^[0-9]{6}$")]
AccountNumber = Annotated[str, Field(pattern=r"^[0-9]{6,25}$")]
AmountVnd = Annotated[int, Field(ge=0, le=100_000_000_000)]


# --------------------------------------------------------------------------- debug


class DebugOverrides(ApiModel):
    """Test-only overrides. Accepted only when ``GUARDIAN_DEBUG=true`` (otherwise 403 DEBUG_DISABLED)."""

    simulate_llm_delay_ms: Annotated[int, Field(ge=0, le=60_000)] | None = None
    simulate_skip_qr_verify: bool = False
    force_llm_output: dict[str, Any] | None = None
    simulate_redactor_failure: bool = False


# --------------------------------------------------------------------------- shared building blocks


class ErrorBody(ApiModel):
    error: str
    message_vi: str = ""
    details: dict[str, Any] = {}


class TrustedContactRef(ApiModel):
    name: str
    phone: str


class UiHints(ApiModel):
    calm_shield: bool = False
    show_context_elicitation: bool = False
    safe_payment_tips: bool = False
    show_transfer_now: bool = False
    handoff_allowed: bool = True
    missing_fields: list[str] = []
    trusted_contacts: list[TrustedContactRef] = []
    hotline: str | None = None


class Signals(ApiModel):
    """Enum and numeric signals only, safe to show in DecisionTrace and Calm Shield."""

    scam_playbook: ScamPlaybook | None = None
    manipulation_cues: Annotated[list[Cue], Field(max_length=6)] = []
    url_flags: list[str] = []
    prefilter_score: Annotated[float, Field(ge=0.0, le=1.0)] | None = None


class QrTag62(ApiModel):
    purpose: str | None = None
    bill_number: str | None = None
    reference: str | None = None


class QrFields(ApiModel):
    payload_format: str | None = None
    poi_method: str | None = None
    aid: str | None = None
    bank_bin: str | None = None
    bank_name: str | None = None
    account_number: str | None = None
    service_code: str | None = None
    amount_vnd: int | None = None
    currency: str | None = None
    country: str | None = None
    tag62: QrTag62 | None = None


class QrCrc(ApiModel):
    expected: str
    computed: str


class QrVerifyRequest(ApiModel):
    payload: Annotated[str, Field(max_length=512)]


class QrVerifyResponse(ApiModel):
    result: QrResult
    flags: list[QrFlag] = []
    fields: QrFields | None = None
    crc: QrCrc | None = None


class Prefill(ApiModel):
    bank_bin: str | None = None
    bank_name: str | None = None
    account_number: str | None = None
    amount_vnd: int | None = None
    memo: str | None = None
    account_origin: AccountOrigin | None = None
    source_integrity_for_flow_a: SourceIntegrity = SourceIntegrity.USER_TYPED


class NameConfirmation(ApiModel):
    pending_id: str
    display_name: str | None = None
    bank_name: str | None = None
    account_digits_spaced: str
    found: bool
    sandbox: bool = True


class ReceiptItemOut(ApiModel):
    name: str
    quantity: int
    unit_price_vnd: int


class ReceiptExtension(ApiModel):
    items: list[ReceiptItemOut] = []
    total_vnd: int | None = None
    items_sum_vnd: int = 0


class ListingExtension(ApiModel):
    product_category: ProductCategory = ProductCategory.OTHER
    product_key: str | None = None
    listed_price_vnd: int | None = None
    reference_price_vnd: int | None = None
    discount_percent: int | None = None
    requires_deposit: bool = False


class OfficialPromo(ApiModel):
    title_vi: str
    valid_to: str


class PromoExtension(ApiModel):
    brand: PromoBrand = PromoBrand.OTHER
    promo_code: str | None = None
    matched: bool = False
    official_promo: OfficialPromo | None = None


class Extensions(ApiModel):
    receipt: ReceiptExtension | None = None
    listing: ListingExtension | None = None
    promo: PromoExtension | None = None


class StageTimings(ApiModel):
    stage2: int | None = None
    stage3: int | None = None
    total: int | None = None


# --------------------------------------------------------------------------- CheckResponse envelope


class CheckResponse(ApiModel):
    """Envelope for Flow A, Flow B, fast-unblock, context and name/confirm."""

    request_id: str
    verdict_id: str
    channel: Channel
    verdict: GuardianVerdict
    ui_hints: UiHints = UiHints()
    qr: QrVerifyResponse | None = None
    prefill: Prefill | None = None
    name_confirmation: NameConfirmation | None = None
    extensions: Extensions | None = None
    signals: Signals = Signals()
    sandbox_sources: list[str] = []
    trace: list[TraceStep] = []
    rules_fired: list[RuleFiring] = []
    stop_codes: list[StopCode] = []
    stage_timings_ms: StageTimings = StageTimings()
    latency_ms: int | None = None


# --------------------------------------------------------------------------- health / wallet


class HealthResponse(ApiModel):
    status: str
    llm_provider: str
    llm_model: str | None = None
    version: str
    sandbox_now: str
    debug: bool
    audit: Literal["ok", "degraded"] | None = None


class SpendingByCategory(ApiModel):
    category: SpendCategory
    label_vi: str
    total_vnd: int


class BudgetOut(ApiModel):
    category: SpendCategory
    label_vi: str
    limit_vnd: int
    spent_vnd: int
    percent_used: int
    status: Literal["OK", "WARNING", "OVER"]


class WalletTransactionOut(ApiModel):
    id: str
    at: datetime
    direction: Literal["IN", "OUT"]
    category: SpendCategory
    counterparty: str
    amount_vnd: int


class BillOut(ApiModel):
    provider_id: str
    provider_name: str
    period: str
    amount_vnd: int
    due_date: str
    status: str


class SubscriptionOut(ApiModel):
    id: str
    name: str
    amount_vnd: int
    renewal_date: str
    last_used_at: datetime | None = None


class BillSpikeAlert(ApiModel):
    type: Literal["BILL_SPIKE"] = "BILL_SPIKE"
    provider_id: str
    current_vnd: int
    avg3_vnd: int
    increase_percent: int


class RenewalSoonAlert(ApiModel):
    type: Literal["RENEWAL_SOON"] = "RENEWAL_SOON"
    subscription_id: str
    renewal_date: str
    amount_vnd: int
    days_left: int


class UnusedSubscriptionAlert(ApiModel):
    type: Literal["UNUSED_SUBSCRIPTION"] = "UNUSED_SUBSCRIPTION"
    subscription_id: str
    days_since_last_use: int


WalletAlert = Annotated[
    BillSpikeAlert | RenewalSoonAlert | UnusedSubscriptionAlert, Field(discriminator="type")
]


class ShieldStatsOut(ApiModel):
    checks: int = 0
    ALLOW: int = 0
    SOFT_FRICTION: int = 0
    HARD_HOLD: int = 0


class WalletSummaryResponse(ApiModel):
    as_of: datetime
    month: str
    sandbox: bool = True
    spending_by_category: list[SpendingByCategory] = []
    budgets: list[BudgetOut] = []
    recent_transactions: list[WalletTransactionOut] = []
    bills: list[BillOut] = []
    subscriptions: list[SubscriptionOut] = []
    alerts: list[WalletAlert] = []
    trusted_contacts: list[TrustedContactRef] = []
    shield_stats: ShieldStatsOut = ShieldStatsOut()


# --------------------------------------------------------------------------- QR encode


class QrEncodeRequest(ApiModel):
    purpose: Literal["BANK_HANDOFF", "SPLIT_BILL"]
    verdict_id: str | None = None
    bank_bin: BankBin
    account_number: AccountNumber
    amount_vnd: AmountVnd | None = None
    memo: Annotated[str, Field(max_length=25)] = ""


class QrEncodeVerify(ApiModel):
    result: QrResult


class QrEncodeResponse(ApiModel):
    payload: str
    verify: QrEncodeVerify
    deeplink: str | None = None


# --------------------------------------------------------------------------- Flow A


class FlowACheckRequest(ApiModel):
    bank_bin: BankBin
    account_number: AccountNumber
    amount_vnd: Annotated[int, Field(gt=0, le=100_000_000_000)]
    memo: Annotated[str, Field(max_length=200)] | None = None
    source_integrity: SourceIntegrity = SourceIntegrity.USER_TYPED
    qr_payload: Annotated[str, Field(max_length=512)] | None = None
    confirmation_token: str | None = None
    origin_verdict_id: str | None = None
    client_time: datetime | None = None
    debug: DebugOverrides | None = None


FastUnblockPurpose = Literal[
    "PAY_FAMILY",
    "PAY_GOODS_SERVICES",
    "PAY_RENT",
    "TUITION",
    "LOAN_REPAYMENT",
    "BUSINESS_PAYMENT",
    "OTHER",
]


class IdentityCheck(ApiModel):
    method: Literal["SANDBOX_OTP"]
    code: Annotated[str, Field(max_length=12)]


class FastUnblockRequest(ApiModel):
    verdict_id: str
    identity_check: IdentityCheck
    purpose: FastUnblockPurpose


ContextChoice = Literal["IN_STORE", "ONLINE_ORDER", "URGENT_RELATIVE", "AUTHORITY_REQUEST"]


class ContextRequest(ApiModel):
    verdict_id: str
    context: ContextChoice


class TransferCommitRequest(ApiModel):
    verdict_id: str
    cooldown_completed: bool
    answered_questions: Annotated[int, Field(ge=0, le=2)] = 0


class TransferCommitResponse(ApiModel):
    status: Literal["SIMULATED_SENT"] = "SIMULATED_SENT"
    ledger_total_24h_vnd: int


# --------------------------------------------------------------------------- precheck / Flow B


class PrecheckRequest(ApiModel):
    text: Annotated[str, Field(max_length=4000)]
    client_time: datetime | None = None


class UrlReport(ApiModel):
    domain: str
    flags: list[str] = []


class PrecheckResponse(ApiModel):
    redacted_text: str
    redaction_counts: dict[str, int] = {}
    prompt_guard_cpu_score: Annotated[float, Field(ge=0.0, le=1.0)]
    urls: list[UrlReport] = []
    hijack_detected: bool = False
    duration_ms: int = 0


class FlowBContent(ApiModel):
    origin: ContentOrigin
    text: Annotated[str, Field(max_length=4000)] | None = None
    qr_payload: Annotated[str, Field(max_length=512)] | None = None


class LinkedTransaction(ApiModel):
    verdict_id: str
    bank_bin: BankBin
    account_number: AccountNumber
    amount_vnd: AmountVnd


class FlowBCheckRequest(ApiModel):
    content: FlowBContent
    mode: ContentMode = ContentMode.GENERAL
    linked_transaction: LinkedTransaction | None = None
    explicit_consent_flag: bool = False
    client_time: datetime | None = None
    debug: DebugOverrides | None = None


class RecipientRiskOut(ApiModel):
    simo_hit: bool
    gnn_mule_score: Annotated[float, Field(ge=0.0, le=1.0)]
    sandbox: bool = True


class FlowBStage2Event(ApiModel):
    event: Literal["stage2"] = "stage2"
    request_id: str
    provisional_tier: DecisionTierName
    provisional_reason_codes: list[str] = []
    red_alert: bool = False
    qr: QrVerifyResponse | None = None
    urls: list[UrlReport] = []
    prefilter_score: Annotated[float, Field(ge=0.0, le=1.0)] = 0.0
    recipient_risk: RecipientRiskOut | None = None
    elapsed_ms: int = 0


class FlowBFinalEvent(ApiModel):
    event: Literal["final"] = "final"
    response: CheckResponse


FlowBEvent = Annotated[FlowBStage2Event | FlowBFinalEvent, Field(discriminator="event")]


# --------------------------------------------------------------------------- name inquiry / confirm


class NameInquiryRequest(ApiModel):
    pending_id: str
    bank_bin: BankBin
    account_number: AccountNumber


class NameInquiryResponse(NameConfirmation):
    pass


class NameConfirmRequest(ApiModel):
    pending_id: str
    confirmed: bool


class NameConfirmResponse(ApiModel):
    confirmation_token: str | None = None
    source_integrity: SourceIntegrity
    check: CheckResponse | None = None


# --------------------------------------------------------------------------- assistant / spend / split


class AssistantCommandRequest(ApiModel):
    text: Annotated[str, Field(max_length=200)]


class SpendQueryRequest(ApiModel):
    category: SpendCategory = SpendCategory.ALL
    period: SpendPeriod = SpendPeriod.THIS_MONTH
    metric: SpendMetric = SpendMetric.TOTAL


class SpendRange(ApiModel):
    from_: datetime = Field(alias="from")
    to: datetime

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class SpendSeriesPoint(ApiModel):
    bucket: str
    value: int


class SpendQueryResponse(ApiModel):
    type: Literal["SPEND_ANSWER"] = "SPEND_ANSWER"
    value: int
    unit: Literal["VND", "COUNT", "PERCENT"] = "VND"
    previous_value: int | None = None
    delta_percent: int | None = None
    range: SpendRange
    series: list[SpendSeriesPoint] = []
    bucket_unit: Literal["DAY", "WEEK"] = "DAY"
    answer_vi: str


class ResolvedContact(ApiModel):
    id: str
    display_name: str
    bank_bin: str
    account_number: str


class TransferResolutionResult(ApiModel):
    type: Literal["TRANSFER_RESOLUTION"] = "TRANSFER_RESOLUTION"
    status: Literal["RESOLVED", "AMBIGUOUS", "NOT_FOUND", "NEEDS_AMOUNT"]
    contact: ResolvedContact | None = None
    candidates: list[ResolvedContact] = []
    prefill: Prefill | None = None
    message_vi: str


class OpenModeResult(ApiModel):
    type: Literal["OPEN_MODE"] = "OPEN_MODE"
    mode: ContentMode
    message_vi: str = ""


class RephraseResult(ApiModel):
    type: Literal["REPHRASE"] = "REPHRASE"
    message_vi: str
    examples_vi: list[str] = []


class AssistantCommandResponse(ApiModel):
    intent: PlannerIntent
    result: Annotated[
        TransferResolutionResult | SpendQueryResponse | OpenModeResult | RephraseResult,
        Field(discriminator="type"),
    ]
    trace: list[TraceStep] = []


class SplitItem(ApiModel):
    name: Annotated[str, Field(min_length=1, max_length=60)]
    quantity: Annotated[int, Field(ge=1, le=99)]
    unit_price_vnd: Annotated[int, Field(ge=0, le=100_000_000)]


class SplitParticipant(ApiModel):
    id: Annotated[str, Field(min_length=1, max_length=20)]
    display_name: Annotated[str, Field(min_length=1, max_length=40)]


class SplitAssignment(ApiModel):
    item_index: Annotated[int, Field(ge=0)]
    participant_ids: Annotated[list[str], Field(min_length=1, max_length=20)]


class SplitComputeRequest(ApiModel):
    items: Annotated[list[SplitItem], Field(min_length=1, max_length=30)]
    receipt_total_vnd: Annotated[int, Field(ge=0)]
    participants: Annotated[list[SplitParticipant], Field(min_length=1, max_length=20)]
    mode: Literal["EQUAL", "BY_ITEM"] = "EQUAL"
    assignments: list[SplitAssignment] | None = None
    payee: Literal["SELF"] = "SELF"
    memo: Annotated[str, Field(max_length=25)] = ""


class SplitShare(ApiModel):
    participant_id: str
    amount_vnd: int
    is_payee: bool
    qr_payload: str | None = None
    qr_status: Literal["VALID_VIETQR", "SKIPPED_PAYEE", "QR_ERROR"]


class SplitComputeResponse(ApiModel):
    status: Literal["OK", "TOTAL_MISMATCH"]
    total_vnd: int
    items_sum_vnd: int
    mismatch_vnd: int
    shares: list[SplitShare] = []


# --------------------------------------------------------------------------- eval / debug


class EvalRunRequest(ApiModel):
    scenario_id: str
    runs: Annotated[int, Field(ge=1, le=20)] = 1


class EvalRunResult(ApiModel):
    passed: bool
    actual: dict[str, Any] = {}
    mismatches: list[str] = []


class EvalRunResponse(ApiModel):
    scenario_id: str
    passed: bool
    runs: list[EvalRunResult] = []


class DebugExtractRequest(ApiModel):
    text: Annotated[str, Field(max_length=4000)]
    mode: ContentMode = ContentMode.GENERAL


class DebugExtractResponse(ApiModel):
    redacted_text: str
    llm_status: str
    extraction: dict[str, Any] | None = None
    latency_ms: int = 0
