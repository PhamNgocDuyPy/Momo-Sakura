"""Control-plane hijack detector for untrusted content. Pure, no network."""

from __future__ import annotations

import re
import unicodedata

from guardian.control_plane.tool_runner import ALLOWED_TOOLS

# "plan" (the Planner call of the assistant) is an everyday English word; naming it is not a hijack.
_COMMON_WORD_TOOLS = frozenset({"plan"})
_TOOL_RE = re.compile(
    r"(?<![A-Za-z0-9_])(?:"
    + "|".join(re.escape(t) for t in sorted(ALLOWED_TOOLS - _COMMON_WORD_TOOLS))
    + r")(?![A-Za-z0-9_])",
    re.IGNORECASE,
)
_FAKE_RC_RE = re.compile(r"\bRC_[A-Z][A-Z0-9_]*")
_VERDICT_KEYS = ("decision_tier", "reason_codes", "allow_fast_unblock", "cooling_off_seconds")
_KEY_RES = tuple(re.compile(rf"[\"']?{k}[\"']?\s*:", re.IGNORECASE) for k in _VERDICT_KEYS)


def detect_hijack(text: str) -> bool:
    """True if text names an internal tool, a fake RC_ code, or mimics a verdict JSON (>= 2 keys)."""
    if not text:
        return False
    norm = unicodedata.normalize("NFC", text)
    if _TOOL_RE.search(norm) or _FAKE_RC_RE.search(norm):
        return True
    return sum(1 for r in _KEY_RES if r.search(norm)) >= 2
