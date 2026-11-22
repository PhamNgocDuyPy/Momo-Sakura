"""Signal -> Reason_Code -> tier mapping (design.md, "Bảng ánh xạ"). Rows S1-S10, X3, X4.

Each function returns a ``Floor``. Thresholds are passed in by the caller (never hard-coded here
except the fixed regulatory constants of Circular 50).
"""

from __future__ import annotations

from collections.abc import Iterable

from guardian.policy.floors import Floor
from guardian.reason_codes import (
    RC_ACCOUNT_SWAP_REQUEST,
    RC_AUTHORITY_COERCION,
    RC_BANK_COACHING_DETECTED,
    RC_C2C_DEPOSIT_URGENCY,
    RC_CIRCULAR50_STRUCTURING_RISK,
    RC_COLD_START_NEEDS_CONTEXT,
    RC_FAKE_SHIPPER_RECALL,
    RC_FAN_IN_VELOCITY_HIGH,
    RC_FLOWB_FLAGGED_RECENTLY,
    RC_GREY_ZONE_RECIPIENT,
    RC_GUARANTEED_RETURN_PIG_BUTCHERING,
    RC_LLM_OUTPUT_INVALID,
    RC_LLM_TIMEOUT_FALLBACK,
    RC_LLM_UNAVAILABLE_FALLBACK,
    RC_MANIPULATION_CUE_REVIEW,
    RC_NO_SCAM_SIGNAL_FOUND,
    RC_OCR_ACCOUNT_NEEDS_CONFIRM,
    RC_PII_EGRESS_BLOCKED,
    RC_PROMPT_INJECTION_BLOCKED,
    RC_QR_CHECK_BYPASS_DETECTED,
    RC_REMOTE_SCREEN_TAKEOVER,
    RC_RISKY_URL_DETECTED,
    RC_SIMO_OR_MULE_HIGH_RISK,
    RC_SUSPECT_INJECTION_REVIEW,
    RC_SUSPICIOUS_UNCLASSIFIED,
    RC_TASK_SCAM_UNLOCK_FEE,
    RC_TRUSTED_PAYEE_HISTORY,
    RC_UNOFFICIAL_APK_PHISHING,
    RC_UNVERIFIED_INBOUND_RECEIPT,
    RC_UPFRONT_FEE_REQUEST,
    RC_URGENT_THIRD_PARTY_ACCT,
    RC_VIETQR_FOREIGN_OR_NON_VND,
    RC_VIETQR_INVALID_FORMAT,
    RC_VIETQR_TAMPERED_BAD_CRC,
)
from guardian.schemas.enums import Cue, DecisionTier, HardSource, QrResult, ScamPlaybook
from guardian.schemas.extraction import QuarantinedExtraction

HARD = DecisionTier.HARD_HOLD
SOFT = DecisionTier.SOFT_FRICTION
ALLOW = DecisionTier.ALLOW

GNN_HARD_THRESHOLD = 0.85
GNN_GREY_LOW = 0.6
GREY_ACCOUNT_AGE_DAYS = 30
R5_MIN_AMOUNT_VND = 9_000_000
R5_MAX_AMOUNT_VND = 10_000_000  # exclusive
R5_TOTAL_24H_VND = 20_000_000


def qr_floor(result: QrResult) -> Floor | None:
    """S1-S3: VietQR_Verifier result -> floor. ``VALID_VIETQR`` yields no floor."""
    if result == QrResult.BAD_CRC:
        return Floor(HARD, RC_VIETQR_TAMPERED_BAD_CRC, "TIER1", HardSource.QR_BAD_CRC)
    if result == QrResult.FOREIGN_OR_NON_VND:
        return Floor(SOFT, RC_VIETQR_FOREIGN_OR_NON_VND, "TIER1")
    if result == QrResult.INVALID_FORMAT:
        return Floor(SOFT, RC_VIETQR_INVALID_FORMAT, "TIER1")
    return None


def r6_floor() -> Floor:
    """S4: QR present but ``verify_vietqr_emvco`` missing from the trace."""
    return Floor(HARD, RC_QR_CHECK_BYPASS_DETECTED, "R6", HardSource.R6_MISSING_QR_CHECK)


def simo_floor() -> Floor:
    """S5."""
    return Floor(HARD, RC_SIMO_OR_MULE_HIGH_RISK, "R4", HardSource.SIMO_HIT)


def gnn_floor() -> Floor:
    """S6: removable by Fast Unblock."""
    return Floor(
        HARD, RC_SIMO_OR_MULE_HIGH_RISK, "R4", HardSource.GNN_MULE, frozenset({"FAST_UNBLOCK"})
    )


def velocity_floor() -> Floor:
    """S7: removable by Fast Unblock."""
    return Floor(
        HARD, RC_FAN_IN_VELOCITY_HIGH, "R4", HardSource.FAN_IN_VELOCITY, frozenset({"FAST_UNBLOCK"})
    )


def grey_zone_floor() -> Floor:
    """S8."""
    return Floor(SOFT, RC_GREY_ZONE_RECIPIENT, "BASELINE")


def memory_floor() -> Floor:
    """S9."""
    return Floor(HARD, RC_FLOWB_FLAGGED_RECENTLY, "MEMORY", HardSource.RISK_MEMORY)


def structuring_floor() -> Floor:
    """S10 (and S11 for Flow B)."""
    return Floor(SOFT, RC_CIRCULAR50_STRUCTURING_RISK, "R5")


def is_structuring(amount_vnd: int, total_24h_vnd: int) -> bool:
    """R5: 9M <= amount < 10M and the 24 h total including this transfer reaches 20M."""
    return (
        R5_MIN_AMOUNT_VND <= amount_vnd < R5_MAX_AMOUNT_VND
        and total_24h_vnd + amount_vnd >= R5_TOTAL_24H_VND
    )


def ocr_confirm_floor() -> Floor:
    """X2 (Flow A abort branch)."""
    return Floor(SOFT, RC_OCR_ACCOUNT_NEEDS_CONFIRM, "R2")


def trusted_payee_floor() -> Floor:
    """X3."""
    return Floor(ALLOW, RC_TRUSTED_PAYEE_HISTORY, "BASELINE")


def cold_start_floor() -> Floor:
    """X4: removable once the user declares an in-store context."""
    return Floor(SOFT, RC_COLD_START_NEEDS_CONTEXT, "COLD_START", None, frozenset({"CONTEXT_IN_STORE"}))


# --------------------------------------------------------------------------- Flow B rows

PREFILTER_SOFT_THRESHOLD = 0.85

URL_HARD_FLAGS = frozenset({"APK_DOWNLOAD", "GOV_SPOOF"})
URL_SOFT_FLAGS = frozenset(
    {"RISKY_TLD", "PUNYCODE", "BRAND_LOOKALIKE", "SHORTENER", "IP_LITERAL", "SAFE_BROWSING_HIT"}
)

# P1-P6: playbook -> (reason code). P7 depends on ``claims_inbound_payment``.
_HARD_PLAYBOOK_CODES: dict[ScamPlaybook, str] = {
    ScamPlaybook.IMPERSONATE_AUTHORITY_VNEID: RC_AUTHORITY_COERCION,
    ScamPlaybook.DEEPFAKE_RELATIVE_EMERGENCY: RC_URGENT_THIRD_PARTY_ACCT,
    ScamPlaybook.PHISHING_LINK_OR_APK_MALWARE: RC_UNOFFICIAL_APK_PHISHING,
    ScamPlaybook.TASK_SCAM_JOB_ONLINE: RC_TASK_SCAM_UNLOCK_FEE,
    ScamPlaybook.INVESTMENT_ROMANCE_PIG_BUTCHERING: RC_GUARANTEED_RETURN_PIG_BUTCHERING,
    ScamPlaybook.FAKE_SHIPPER_RECALL: RC_FAKE_SHIPPER_RECALL,
}

_MANIPULATION_CUES = frozenset(
    {
        Cue.URGENCY_TIME_PRESSURE,
        Cue.SECRECY_DO_NOT_TELL_ANYONE,
        Cue.COACHING_WHAT_TO_TELL_BANK,
        Cue.SCREEN_SHARE_OR_REMOTE_APP,
        Cue.GUARANTEED_HIGH_RETURN,
    }
)

# Rows a degraded (timeout / error) heuristic is allowed to emit: P8, P9, C3, C4.
FALLBACK_REASON_CODES = frozenset(
    {
        RC_C2C_DEPOSIT_URGENCY,
        RC_SUSPICIOUS_UNCLASSIFIED,
        RC_MANIPULATION_CUE_REVIEW,
        RC_UPFRONT_FEE_REQUEST,
    }
)


def prefilter_floor() -> Floor:
    """S12: R3 soft level. Prefilter alone never reaches HARD_HOLD."""
    return Floor(SOFT, RC_SUSPECT_INJECTION_REVIEW, "R3")


def injection_floor() -> Floor:
    """S13: ``contains_prompt_injection`` from the Quarantined extraction."""
    return Floor(HARD, RC_PROMPT_INJECTION_BLOCKED, "R3", HardSource.PROMPT_INJECTION)


def hijack_floor() -> Floor:
    """S14: control plane hijack attempt."""
    return Floor(HARD, RC_PROMPT_INJECTION_BLOCKED, "R3", HardSource.CONTROL_PLANE_HIJACK)


def url_floors(flag_sets: Iterable[Iterable[str]]) -> list[Floor]:
    """S15 / S16 over every URL in the content (at most one floor per row)."""
    flags: set[str] = set()
    for fs in flag_sets:
        flags.update(fs)
    floors: list[Floor] = []
    if flags & URL_HARD_FLAGS:
        floors.append(Floor(HARD, RC_UNOFFICIAL_APK_PHISHING, "URL", HardSource.URL_APK_OR_GOV_SPOOF))
    if flags & URL_SOFT_FLAGS:
        floors.append(Floor(SOFT, RC_RISKY_URL_DETECTED, "URL"))
    return floors


def pii_egress_floor() -> Floor:
    """L4."""
    return Floor(SOFT, RC_PII_EGRESS_BLOCKED, "R1")


def llm_invalid_floor() -> Floor:
    """L1."""
    return Floor(SOFT, RC_LLM_OUTPUT_INVALID, "LLM_FALLBACK")


def llm_timeout_floor() -> Floor:
    """L2."""
    return Floor(SOFT, RC_LLM_TIMEOUT_FALLBACK, "LLM_FALLBACK")


def llm_unavailable_floor() -> Floor:
    """L3."""
    return Floor(SOFT, RC_LLM_UNAVAILABLE_FALLBACK, "LLM_FALLBACK")


def account_swap_floor() -> Floor:
    """X1."""
    return Floor(SOFT, RC_ACCOUNT_SWAP_REQUEST, "BASELINE")


def no_scam_signal_floor() -> Floor:
    """P10."""
    return Floor(ALLOW, RC_NO_SCAM_SIGNAL_FOUND, "BASELINE")


def is_hard_playbook(extraction: QuarantinedExtraction) -> bool:
    """True when the playbook row (P1-P7) yields a HARD floor."""
    playbook = extraction.scam_playbook
    if playbook in _HARD_PLAYBOOK_CODES:
        return True
    return (
        playbook == ScamPlaybook.C2C_DEPOSIT_OR_FAKE_RECEIPT
        and extraction.payment_request is not None
        and extraction.payment_request.claims_inbound_payment
    )


def playbook_floors(extraction: QuarantinedExtraction) -> list[Floor]:
    """P1-P9. ``NONE_DETECTED`` yields nothing here (P10 is added last by the engine).

    ``UNKNOWN_SUSPICIOUS`` is capped at SOFT_FRICTION (P9).
    """
    playbook = extraction.scam_playbook
    if playbook == ScamPlaybook.NONE_DETECTED:
        return []
    if playbook in _HARD_PLAYBOOK_CODES:
        return [Floor(HARD, _HARD_PLAYBOOK_CODES[playbook], "PLAYBOOK", HardSource.PLAYBOOK_HARD)]
    if playbook == ScamPlaybook.C2C_DEPOSIT_OR_FAKE_RECEIPT:
        if is_hard_playbook(extraction):
            return [Floor(HARD, RC_UNVERIFIED_INBOUND_RECEIPT, "PLAYBOOK", HardSource.PLAYBOOK_HARD)]
        return [Floor(SOFT, RC_C2C_DEPOSIT_URGENCY, "PLAYBOOK")]
    return [Floor(SOFT, RC_SUSPICIOUS_UNCLASSIFIED, "PLAYBOOK")]  # UNKNOWN_SUSPICIOUS


def cue_floors(extraction: QuarantinedExtraction) -> list[Floor]:
    """S11 and C1-C4 (design decision D2).

    A cue alone never creates HARD. The HARD codes of C1/C2 require a playbook already in the
    HARD group, so Req 15.7 keeps holding.
    """
    cues = set(extraction.manipulation_cues)
    hard_playbook = is_hard_playbook(extraction)
    floors: list[Floor] = []

    if Cue.SPLIT_TRANSFER_UNDER_10M in cues:
        floors.append(structuring_floor())

    if hard_playbook:
        if Cue.COACHING_WHAT_TO_TELL_BANK in cues:
            floors.append(
                Floor(HARD, RC_BANK_COACHING_DETECTED, "PLAYBOOK", HardSource.PLAYBOOK_HARD)
            )
        if Cue.SCREEN_SHARE_OR_REMOTE_APP in cues:
            floors.append(
                Floor(HARD, RC_REMOTE_SCREEN_TAKEOVER, "PLAYBOOK", HardSource.PLAYBOOK_HARD)
            )
    elif cues & _MANIPULATION_CUES:
        floors.append(Floor(SOFT, RC_MANIPULATION_CUE_REVIEW, "CUE"))

    if Cue.UPFRONT_DEPOSIT_OR_UNLOCK_FEE in cues and extraction.scam_playbook not in (
        ScamPlaybook.TASK_SCAM_JOB_ONLINE,
        ScamPlaybook.C2C_DEPOSIT_OR_FAKE_RECEIPT,
    ):
        floors.append(Floor(SOFT, RC_UPFRONT_FEE_REQUEST, "CUE"))
    return floors


def fallback_floors(extraction: QuarantinedExtraction) -> list[Floor]:
    """Heuristic fallback (L2/L3/L4): only SOFT rows P8, P9, C3, C4; never P1-P7, C1, C2.

    A HARD-group playbook coming from a heuristic is reported as P9 (unclassified, SOFT).
    """
    playbook = extraction.scam_playbook
    floors: list[Floor] = []
    if playbook == ScamPlaybook.C2C_DEPOSIT_OR_FAKE_RECEIPT:
        floors.append(Floor(SOFT, RC_C2C_DEPOSIT_URGENCY, "PLAYBOOK"))
    elif playbook != ScamPlaybook.NONE_DETECTED:
        floors.append(Floor(SOFT, RC_SUSPICIOUS_UNCLASSIFIED, "PLAYBOOK"))

    cues = set(extraction.manipulation_cues)
    if cues & _MANIPULATION_CUES:
        floors.append(Floor(SOFT, RC_MANIPULATION_CUE_REVIEW, "CUE"))
    if Cue.UPFRONT_DEPOSIT_OR_UNLOCK_FEE in cues and playbook not in (
        ScamPlaybook.TASK_SCAM_JOB_ONLINE,
        ScamPlaybook.C2C_DEPOSIT_OR_FAKE_RECEIPT,
    ):
        floors.append(Floor(SOFT, RC_UPFRONT_FEE_REQUEST, "CUE"))
    return floors
