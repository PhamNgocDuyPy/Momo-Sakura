"""Deterministic entity scanner: account numbers, bank aliases -> BIN, amounts, URLs.

Runs before the LLM so Stage 2 has data for risk lookups. Pure local computation.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from functools import lru_cache

from guardian.tools.amount import find_amounts
from guardian.tools.banks import all_aliases
from guardian.tools.pii import _fold_chars, is_account_context
from guardian.tools.url_checker import UrlCheckResult, check_urls

_ACCOUNT_RE = re.compile(r"(?<!\d)\d{6,19}(?!\d)")
_BANK_NEAR_CHARS = 40


@dataclass(frozen=True)
class BankMention:
    alias: str  # folded alias as matched
    bin: str
    start: int
    end: int


@dataclass(frozen=True)
class AccountMention:
    account_number: str
    start: int
    end: int
    bank_bin: str | None = None  # nearest bank mention, if any


@dataclass(frozen=True)
class ScannedEntities:
    accounts: tuple[AccountMention, ...] = ()
    banks: tuple[BankMention, ...] = ()
    amounts: tuple[int, ...] = ()
    urls: tuple[UrlCheckResult, ...] = ()
    bank_bins: tuple[str, ...] = field(default=())


@lru_cache(maxsize=1)
def _alias_regex() -> tuple[re.Pattern[str], dict[str, str]]:
    try:
        aliases = all_aliases()
    except RuntimeError:
        aliases = {}
    if not aliases:
        return re.compile(r"(?!x)x"), {}
    alts = sorted(aliases, key=len, reverse=True)
    pattern = re.compile(r"(?<![a-z0-9])(?:" + "|".join(re.escape(a) for a in alts) + r")(?![a-z0-9])")
    return pattern, aliases


def _scan_banks(folded_lower: str) -> list[BankMention]:
    pattern, aliases = _alias_regex()
    return [BankMention(m.group(), aliases[m.group()], m.start(), m.end()) for m in pattern.finditer(folded_lower)]


def _nearest_bin(start: int, end: int, banks: list[BankMention]) -> str | None:
    best: tuple[int, str] | None = None
    for bank in banks:
        dist = max(bank.start - end, start - bank.end, 0)
        if dist <= _BANK_NEAR_CHARS and (best is None or dist < best[0]):
            best = (dist, bank.bin)
    return best[1] if best else None


def scan_entities(text: str) -> ScannedEntities:
    """Extract entities from ``text``. Never raises on arbitrary input."""
    if not isinstance(text, str) or not text:
        return ScannedEntities()
    nfc = unicodedata.normalize("NFC", text)
    # Folding keeps string length, so offsets are shared with ``nfc``.
    folded_lower = _fold_chars(nfc).lower()

    banks = _scan_banks(folded_lower)
    accounts: list[AccountMention] = []
    for m in _ACCOUNT_RE.finditer(nfc):
        if not is_account_context(nfc, m.start()):
            continue
        accounts.append(AccountMention(m.group(), m.start(), m.end(), _nearest_bin(m.start(), m.end(), banks)))

    bins = tuple(dict.fromkeys(b.bin for b in banks))
    return ScannedEntities(
        accounts=tuple(accounts),
        banks=tuple(banks),
        amounts=tuple(find_amounts(nfc)),
        urls=tuple(check_urls(nfc)),
        bank_bins=bins,
    )
