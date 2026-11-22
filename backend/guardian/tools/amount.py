"""Amount_Parser and Amount_Formatter for Vietnamese money expressions.

Mirrors ``web/src/lib/amount.ts``. Pure functions, never raise on bad input.
"""

from __future__ import annotations

import re
import unicodedata
from fractions import Fraction

_NUM = r"\d+(?:[.,]\d+)?"
_GROUPED = r"\d{1,3}(?:\.\d{3})+"

_RE_LIT = re.compile(r"^(\d+)\s*(?:lít|lit)$")
_RE_XI = re.compile(r"^(\d+)\s*(?:xị|xi)$")
_RE_CU = re.compile(r"^(\d+)\s*(?:củ|cu)$")
_RE_K = re.compile(rf"^({_NUM})\s*(?:k|nghìn|ngàn|nghin|ngan)$")
_RE_TR_DIGITS = re.compile(r"^(\d+)\s*(?:tr|triệu|trieu)\s*(\d{1,3})$")
_RE_TR = re.compile(rf"^({_NUM})\s*(?:tr|triệu|trieu|m)$")
_RE_GROUPED = re.compile(rf"^({_GROUPED})\s*(?:đ|vnd|vnđ|d)?$")
_RE_PLAIN = re.compile(r"^(\d+)\s*(?:đ|vnd|vnđ|d)?$")

# In-sentence scan: only units, thousand separators or explicit currency suffixes
# count as amounts. Bare digit runs (e.g. account numbers) never match.
_UNIT = r"(?:tr|triệu|trieu)"
_SCAN_RE = re.compile(
    r"(?<![\w.,])(?:"
    rf"\d+\s*{_UNIT}\s*\d{{1,3}}"
    rf"|{_NUM}\s*(?:tr|triệu|trieu|m|k|nghìn|ngàn|nghin|ngan)"
    r"|\d+\s*(?:lít|lit|xị|xi|củ|cu)"
    rf"|{_GROUPED}(?:\s*(?:đ|vnd|vnđ))?"
    r"|\d+\s*(?:đ|vnd|vnđ)"
    r")(?![\w])(?![.,]\d)"
)


def _normalize(text: str) -> str:
    return unicodedata.normalize("NFC", text.strip().lower())


def _to_int(value: Fraction) -> int | None:
    if value < 0 or value.denominator != 1:
        return None
    return int(value)


def _decimal(raw: str) -> Fraction:
    return Fraction(raw.replace(",", "."))


def _parse_normalized(s: str) -> int | None:
    m = _RE_LIT.match(s) or _RE_XI.match(s)
    if m:
        return int(m.group(1)) * 100_000
    m = _RE_CU.match(s)
    if m:
        return int(m.group(1)) * 1_000_000
    m = _RE_K.match(s)
    if m:
        return _to_int(_decimal(m.group(1)) * 1000)
    m = _RE_TR_DIGITS.match(s)
    if m:
        a, b = m.group(1), m.group(2)
        return int(a) * 1_000_000 + int(b) * 10 ** (6 - len(b))
    m = _RE_TR.match(s)
    if m:
        return _to_int(_decimal(m.group(1)) * 1_000_000)
    m = _RE_GROUPED.match(s)
    if m:
        return int(m.group(1).replace(".", ""))
    m = _RE_PLAIN.match(s)
    if m:
        return int(m.group(1))
    return None


def parse_amount(text: str) -> int | None:
    """Parse a Vietnamese amount string into integer VND, or ``None``."""
    if not isinstance(text, str):
        return None
    try:
        return _parse_normalized(_normalize(text))
    except (ValueError, ZeroDivisionError):
        return None


def find_amounts(text: str) -> list[int]:
    """Return integer VND amounts found in a sentence, in order of appearance."""
    if not isinstance(text, str):
        return []
    found: list[int] = []
    for m in _SCAN_RE.finditer(_normalize(text)):
        value = _parse_normalized(m.group(0).strip())
        if value is not None:
            found.append(value)
    return found


def format_vnd(n: int) -> str:
    """Format a non-negative integer as ``1.234.567 đ``."""
    if isinstance(n, bool) or not isinstance(n, int) or n < 0:
        raise ValueError("format_vnd expects a non-negative integer")
    return f"{n:,}".replace(",", ".") + " đ"
