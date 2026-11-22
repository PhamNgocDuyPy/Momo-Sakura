"""Grounding check for strings extracted by the Quarantined LLM.

An extracted string may only be used (e.g. to prefill a memo) when, after NFC
normalization and whitespace collapsing, it is a substring of the PII-redacted
source text and contains none of the characters ``[ ] < >``.
"""

from __future__ import annotations

import re
import unicodedata

FORBIDDEN_CHARS: frozenset[str] = frozenset("[]<>")

_WS_RE = re.compile(r"\s+")


def normalize(text: str) -> str:
    """NFC-normalize and collapse runs of whitespace; strip the ends."""
    return _WS_RE.sub(" ", unicodedata.normalize("NFC", text)).strip()


def ground_string(candidate: str | None, redacted_text: str) -> str | None:
    """Return the normalized candidate if grounded, otherwise ``None``."""
    if candidate is None:
        return None
    norm = normalize(candidate)
    if not norm:
        return None
    if any(ch in FORBIDDEN_CHARS for ch in norm):
        return None
    if norm not in normalize(redacted_text):
        return None
    return norm


def is_grounded(candidate: str | None, redacted_text: str) -> bool:
    return ground_string(candidate, redacted_text) is not None
