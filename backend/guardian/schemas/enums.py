"""Shared enums for MoMo Guardian (single source of truth for the API and policy layers)."""

from __future__ import annotations

from enum import IntEnum, StrEnum, auto
from typing import Annotated, Any

from pydantic import BeforeValidator, PlainSerializer


class DecisionTier(IntEnum):
    """Severity order. Serialized by name through ``DecisionTierName``."""

    ALLOW = 0
    SOFT_FRICTION = 1
    HARD_HOLD = 2


def _tier_from_any(value: Any) -> Any:
    if isinstance(value, str):
        try:
            return DecisionTier[value]
        except KeyError as exc:
            raise ValueError(f"unknown DecisionTier: {value}") from exc
    return value


# Use this annotated type in Pydantic models so JSON carries the tier name, not the int.
DecisionTierName = Annotated[
    DecisionTier,
    BeforeValidator(_tier_from_any),
    PlainSerializer(lambda t: t.name, return_type=str),
]


class HardSource(StrEnum):
    """Allowed sources for a HARD_HOLD floor. Re-exported from ``policy/floors.py``."""

    PROMPT_INJECTION = auto()
    CONTROL_PLANE_HIJACK = auto()
    SIMO_HIT = auto()
    GNN_MULE = auto()
    FAN_IN_VELOCITY = auto()
    QR_BAD_CRC = auto()
    URL_APK_OR_GOV_SPOOF = auto()
    R6_MISSING_QR_CHECK = auto()
    RISK_MEMORY = auto()
    PLAYBOOK_HARD = auto()
    PROMO_FAKE = auto()


class SourceIntegrity(StrEnum):
    USER_TYPED = "USER_TYPED"
    VALID_VIETQR_CRC = "VALID_VIETQR_CRC"
    OCR_CONFIRMED_BY_USER = "OCR_CONFIRMED_BY_USER"
    OCR_UNCONFIRMED = "OCR_UNCONFIRMED"


class AccountOrigin(StrEnum):
    TYPED = "TYPED"
    PASTE = "PASTE"
    CLIPBOARD = "CLIPBOARD"
    OCR = "OCR"
    QR = "QR"
    SHARE = "SHARE"
    CONTACT = "CONTACT"


class ContentOrigin(StrEnum):
    PASTE = "PASTE"
    CLIPBOARD = "CLIPBOARD"
    OCR = "OCR"
    QR_CAMERA = "QR_CAMERA"
    QR_IMAGE = "QR_IMAGE"
    SHARE_TARGET = "SHARE_TARGET"
    CONTEXT_CHAT = "CONTEXT_CHAT"
    EXTENSION_SELECTION = "EXTENSION_SELECTION"
    EXTENSION_PAGE_TEXT = "EXTENSION_PAGE_TEXT"


class ContentMode(StrEnum):
    GENERAL = "GENERAL"
    SPLIT_BILL = "SPLIT_BILL"
    SHOP = "SHOP"
    PROMO = "PROMO"


class QrResult(StrEnum):
    VALID_VIETQR = "VALID_VIETQR"
    BAD_CRC = "BAD_CRC"
    FOREIGN_OR_NON_VND = "FOREIGN_OR_NON_VND"
    INVALID_FORMAT = "INVALID_FORMAT"


class QrFlag(StrEnum):
    UTF8_BYTE_FALLBACK = "UTF8_BYTE_FALLBACK"
    LEGACY_DEFAULT_SERVICE_CODE = "LEGACY_DEFAULT_SERVICE_CODE"


class ScamPlaybook(StrEnum):
    NONE_DETECTED = "NONE_DETECTED"
    IMPERSONATE_AUTHORITY_VNEID = "IMPERSONATE_AUTHORITY_VNEID"
    FAKE_SHIPPER_RECALL = "FAKE_SHIPPER_RECALL"
    C2C_DEPOSIT_OR_FAKE_RECEIPT = "C2C_DEPOSIT_OR_FAKE_RECEIPT"
    TASK_SCAM_JOB_ONLINE = "TASK_SCAM_JOB_ONLINE"
    INVESTMENT_ROMANCE_PIG_BUTCHERING = "INVESTMENT_ROMANCE_PIG_BUTCHERING"
    DEEPFAKE_RELATIVE_EMERGENCY = "DEEPFAKE_RELATIVE_EMERGENCY"
    PHISHING_LINK_OR_APK_MALWARE = "PHISHING_LINK_OR_APK_MALWARE"
    UNKNOWN_SUSPICIOUS = "UNKNOWN_SUSPICIOUS"


class Cue(StrEnum):
    URGENCY_TIME_PRESSURE = "URGENCY_TIME_PRESSURE"
    SECRECY_DO_NOT_TELL_ANYONE = "SECRECY_DO_NOT_TELL_ANYONE"
    COACHING_WHAT_TO_TELL_BANK = "COACHING_WHAT_TO_TELL_BANK"
    UPFRONT_DEPOSIT_OR_UNLOCK_FEE = "UPFRONT_DEPOSIT_OR_UNLOCK_FEE"
    GUARANTEED_HIGH_RETURN = "GUARANTEED_HIGH_RETURN"
    SCREEN_SHARE_OR_REMOTE_APP = "SCREEN_SHARE_OR_REMOTE_APP"
    SPLIT_TRANSFER_UNDER_10M = "SPLIT_TRANSFER_UNDER_10M"


class Confidence(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class Intent(StrEnum):
    TRANSFER = "TRANSFER"
    SPLIT_BILL = "SPLIT_BILL"
    SPEND_QUERY = "SPEND_QUERY"
    CHECK_PROMO = "CHECK_PROMO"
    SHOP_CHECK = "SHOP_CHECK"
    CHECK_CONTENT = "CHECK_CONTENT"
    UNKNOWN = "UNKNOWN"


class ProductCategory(StrEnum):
    PHONE = "PHONE"
    LAPTOP = "LAPTOP"
    TABLET = "TABLET"
    HEADPHONES = "HEADPHONES"
    SMARTWATCH = "SMARTWATCH"
    GAME_CONSOLE = "GAME_CONSOLE"
    CAMERA = "CAMERA"
    SNEAKERS = "SNEAKERS"
    EVENT_TICKET = "EVENT_TICKET"
    OTHER = "OTHER"


class PromoBrand(StrEnum):
    MOMO = "MOMO"
    SHOPEE = "SHOPEE"
    LAZADA = "LAZADA"
    TIKI = "TIKI"
    TIKTOK_SHOP = "TIKTOK_SHOP"
    GRAB = "GRAB"
    BANK = "BANK"
    OTHER = "OTHER"


class StopCode(StrEnum):
    ABORT_WAIT_NAPAS_NAME_USER_CONFIRM = "ABORT_WAIT_NAPAS_NAME_USER_CONFIRM"
    TEMPORAL_BYPASS_DETECTED_MISSING_VIETQR_CHECK = "TEMPORAL_BYPASS_DETECTED_MISSING_VIETQR_CHECK"
    LAW_91_CONSENT_REQUIRED = "LAW_91_CONSENT_REQUIRED"
    PII_EGRESS_BLOCKED = "PII_EGRESS_BLOCKED"


class SpendCategory(StrEnum):
    ALL = "ALL"
    CAFE = "CAFE"
    FOOD = "FOOD"
    GROCERY = "GROCERY"
    TRANSPORT = "TRANSPORT"
    SHOPPING = "SHOPPING"
    BILLS = "BILLS"
    SUBSCRIPTION = "SUBSCRIPTION"
    ENTERTAINMENT = "ENTERTAINMENT"
    HEALTH = "HEALTH"
    EDUCATION = "EDUCATION"
    TRANSFER_OUT = "TRANSFER_OUT"

    @property
    def label_vi(self) -> str:
        return SPEND_CATEGORY_LABELS_VI[self]


class SpendPeriod(StrEnum):
    TODAY = "TODAY"
    YESTERDAY = "YESTERDAY"
    THIS_WEEK = "THIS_WEEK"
    LAST_WEEK = "LAST_WEEK"
    THIS_MONTH = "THIS_MONTH"
    LAST_MONTH = "LAST_MONTH"
    LAST_7_DAYS = "LAST_7_DAYS"
    LAST_30_DAYS = "LAST_30_DAYS"
    LAST_3_MONTHS = "LAST_3_MONTHS"

    @property
    def label_vi(self) -> str:
        return SPEND_PERIOD_LABELS_VI[self]


class SpendMetric(StrEnum):
    TOTAL = "TOTAL"
    COUNT = "COUNT"
    AVERAGE_PER_TXN = "AVERAGE_PER_TXN"
    AVERAGE_PER_DAY = "AVERAGE_PER_DAY"
    MAX_TXN = "MAX_TXN"
    COMPARE_PREVIOUS = "COMPARE_PREVIOUS"

    @property
    def label_vi(self) -> str:
        return SPEND_METRIC_LABELS_VI[self]


SPEND_CATEGORY_LABELS_VI: dict[SpendCategory, str] = {
    SpendCategory.ALL: "Tất cả",
    SpendCategory.CAFE: "Cà phê",
    SpendCategory.FOOD: "Ăn uống",
    SpendCategory.GROCERY: "Đi chợ / siêu thị",
    SpendCategory.TRANSPORT: "Di chuyển",
    SpendCategory.SHOPPING: "Mua sắm",
    SpendCategory.BILLS: "Hóa đơn điện/nước/internet",
    SpendCategory.SUBSCRIPTION: "Gói định kỳ",
    SpendCategory.ENTERTAINMENT: "Giải trí",
    SpendCategory.HEALTH: "Sức khỏe",
    SpendCategory.EDUCATION: "Học tập",
    SpendCategory.TRANSFER_OUT: "Chuyển tiền",
}

SPEND_PERIOD_LABELS_VI: dict[SpendPeriod, str] = {
    SpendPeriod.TODAY: "hôm nay",
    SpendPeriod.YESTERDAY: "hôm qua",
    SpendPeriod.THIS_WEEK: "tuần này",
    SpendPeriod.LAST_WEEK: "tuần trước",
    SpendPeriod.THIS_MONTH: "tháng này",
    SpendPeriod.LAST_MONTH: "tháng trước",
    SpendPeriod.LAST_7_DAYS: "7 ngày qua",
    SpendPeriod.LAST_30_DAYS: "30 ngày qua",
    SpendPeriod.LAST_3_MONTHS: "3 tháng qua",
}

SPEND_METRIC_LABELS_VI: dict[SpendMetric, str] = {
    SpendMetric.TOTAL: "Tổng chi",
    SpendMetric.COUNT: "Số lần chi",
    SpendMetric.AVERAGE_PER_TXN: "Trung bình mỗi lần",
    SpendMetric.AVERAGE_PER_DAY: "Trung bình mỗi ngày",
    SpendMetric.MAX_TXN: "Lần chi lớn nhất",
    SpendMetric.COMPARE_PREVIOUS: "So với kỳ trước",
}
