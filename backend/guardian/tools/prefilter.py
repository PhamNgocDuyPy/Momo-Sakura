"""CPU prompt-injection prefilter. Pure, deterministic, no network."""

from __future__ import annotations

import re
import unicodedata

PREFILTER_SOFT_THRESHOLD: float = 0.85

_FLAGS = re.IGNORECASE

# Internal tool names (kept literal to avoid importing the control plane).
_TOOL_NAMES = (
    "verify_vietqr_emvco|check_urls|prompt_guard_cpu_score|redact_pii_local|"
    "scan_entities|detect_hijack|napas_name_inquiry_readonly|"
    "lookup_recipient_risk_and_simo|lookup_payer_history|risk_memory_lookup|"
    "risk_memory_write|quarantined_extract|lookup_official_promos|"
    "lookup_reference_price"
)

# (name, compiled regex, weight in (0, 1)); weights per design.md.
FEATURES: tuple[tuple[str, re.Pattern[str], float], ...] = (
    (
        "ignore_instructions",
        re.compile(
            # Matched on diacritic-folded text (see _fold).
            r"bo\s*qua\s+(?:moi|tat\s*ca)\s+(?:huong\s*dan|chi\s*dan)"
            r"|ignore\s+(?:all|previous)\s+instructions",
            _FLAGS,
        ),
        0.7,
    ),
    ("role_prefix", re.compile(r"(?:^|\n)\s*(?:system|assistant)\s*:|<\s*system\s*>", _FLAGS), 0.6),
    (
        "verdict_json_keys",
        re.compile(r"[\"']?(?:decision_tier|reason_codes|scam_playbook)[\"']?\s*:", _FLAGS),
        0.6,
    ),
    ("invisible_chars", re.compile("[\u200b\u200c\u200d\u2060\ufeff\u202a-\u202e\u2066-\u2069]"), 0.5),
    ("persona_override", re.compile(r"ban\s+la\s+(?:ai|tro\s*ly)|you\s+are\s+now", _FLAGS), 0.4),
    ("base64_block", re.compile(r"[A-Za-z0-9+/]{200,}={0,2}"), 0.3),
    ("tool_name", re.compile(rf"\b(?:{_TOOL_NAMES})\b", _FLAGS), 0.6),
)


def _fold(text: str) -> str:
    """Strip Vietnamese diacritics (NFD, drop marks, đ->d) so patterns are accent-insensitive."""
    nfd = unicodedata.normalize("NFD", text)
    stripped = "".join(c for c in nfd if unicodedata.category(c) != "Mn")
    return stripped.replace("đ", "d").replace("Đ", "D")


def prompt_guard_cpu_score(text: str) -> float:
    """Return 1 - prod(1 - w_i) over matched features, always within [0, 1]."""
    if not text:
        return 0.0
    norm = _fold(text)
    remaining = 1.0
    for _name, pattern, weight in FEATURES:
        if pattern.search(norm):
            remaining *= 1.0 - weight
    return min(1.0, max(0.0, 1.0 - remaining))


def exceeds_soft_threshold(score: float, threshold: float = PREFILTER_SOFT_THRESHOLD) -> bool:
    return score >= threshold

