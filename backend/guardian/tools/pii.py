"""PII_Redactor: the single PII detector shared by redaction and the R1 egress guard.

Pure local computation. This module must never import network libraries.
Spans refer to the NFC-normalised text (``detect_pii`` normalises its input).
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass
from functools import lru_cache
from typing import Final

from guardian.tools.banks import all_aliases

PII_KINDS: Final = ("OTP", "CCCD", "CMND", "SDT", "TEN")

ACCOUNT_WINDOW: Final = 25
_MAX_ROUNDS: Final = 10

# Kinship terms stay visible so playbook rules ("Mẹ ơi...") still work.
KINSHIP_TERMS: Final = frozenset(
    {"me", "ma", "bo", "ba", "cha", "anh", "chi", "em", "con", "chau", "ong", "ba", "co", "chu", "bac", "di"}
)
_KEYWORD_WORDS: Final = frozenset({"cccd", "cmnd", "stk", "sdt", "otp", "tk", "bank"})

_CCCD_RE = re.compile(r"(?<!\d)\d{12}(?!\d)")
_CMND_RE = re.compile(r"(?<!\d)\d{9}(?!\d)")
_SDT_RE = re.compile(r"(?<!\d)(?:\+?84|0)(?:3|5|7|8|9)\d(?:[\s.-]?\d){7}(?!\d)")
_OTP_RE = re.compile(r"(?<![a-z0-9])(?:otp|ma xac (?:thuc|nhan))[^\d\n]{0,12}(?<!\d)(\d{4,8})(?!\d)", re.I)
_ACCOUNT_DIGITS_RE = re.compile(r"(?<!\d)\d{6,19}(?!\d)")
_TITLE_RE = re.compile(
    r"(?<!\w)(?:anh|em|chị|ông|ong|bà|cô|chú|bác|tên|ten"
    r"|chủ[ \t]+tài[ \t]+khoản|chu[ \t]+tai[ \t]+khoan|người[ \t]+nhận|nguoi[ \t]+nhan)(?!\w)",
    re.I,
)
_WORD_RE = re.compile(r"[^\W\d_]+")
_TITLE_SEP_RE = re.compile(r"[ \t:]+")
_UPPER_SEP_RE = re.compile(r"[ \t,:\-]*")
_BLANKS_RE = re.compile(r"[ \t]+")
_STRONG_RE = re.compile(
    r"(?<![a-z0-9])(?:cccd|cmnd|can cuoc|chung minh|sdt|so dien thoai|otp)(?![a-z])"
)
_ACCOUNT_KW = ("stk", "so tai khoan", "tai khoan", "tk")
_TOKEN_RE = re.compile(r"\[(OTP|CCCD|CMND|SDT|TEN)_(\d+)\]")


@dataclass(frozen=True)
class PiiSpan:
    start: int
    end: int
    kind: str
    value: str


def _fold_chars(text: str) -> str:
    """Strip diacritics while preserving case and string length (1 char -> 1 char)."""
    out: list[str] = []
    for ch in text:
        if ch == "đ":
            out.append("d")
        elif ch == "Đ":
            out.append("D")
        else:
            base = "".join(c for c in unicodedata.normalize("NFD", ch) if unicodedata.category(c) != "Mn")
            out.append(base if len(base) == 1 else ch)
    return "".join(out)


def _fold_word(word: str) -> str:
    return _fold_chars(unicodedata.normalize("NFC", word)).lower()


@lru_cache(maxsize=1)
def _bank_vocab() -> tuple[re.Pattern[str] | None, frozenset[str]]:
    """(account-context regex over folded text, single-word bank tokens)."""
    try:
        aliases = all_aliases()
    except RuntimeError:
        aliases = {}
    alts = sorted({*_ACCOUNT_KW, *aliases}, key=len, reverse=True)
    pattern = re.compile(r"(?<![a-z0-9])(?:" + "|".join(re.escape(a) for a in alts) + r")(?![a-z0-9])")
    singles = frozenset(a for a in aliases if " " not in a)
    return pattern, singles


def _stop_words() -> frozenset[str]:
    return KINSHIP_TERMS | _KEYWORD_WORDS | _bank_vocab()[1]


def _account_exempt(folded: str, start: int) -> bool:
    """Req 10.5: account-context number is kept unless a strong PII keyword is nearby."""
    window = folded[max(0, start - ACCOUNT_WINDOW) : start].lower()
    if _STRONG_RE.search(window):
        return False
    return _bank_vocab()[0].search(window) is not None  # type: ignore[union-attr]


def is_account_context(text: str, start: int) -> bool:
    """True when the number starting at ``start`` in ``text`` has account context (Req 10.5).

    ``text`` must be the NFC-normalised text so that offsets match ``detect_pii`` spans.
    """
    return _account_exempt(_fold_chars(text), start)


def normalize_contact_names(names: Iterable[str]) -> tuple[str, ...]:
    """Drop kinship-led and too-short variants; NFC-normalise; dedupe."""
    stop = _stop_words()
    kept: dict[str, None] = {}
    for raw in names:
        name = " ".join(unicodedata.normalize("NFC", raw).split())
        words = name.split(" ")
        if len(name) < 2 or _fold_word(words[0]) in KINSHIP_TERMS:
            continue
        if len(words) == 1 and _fold_word(name) in stop:
            continue
        kept[name] = None
    return tuple(kept)


def contact_name_variants(contacts: Iterable[object]) -> tuple[str, ...]:
    """Full names, given names (last word) and aliases from WalletDataProvider contacts."""
    variants: list[str] = []
    for contact in contacts:
        display = str(getattr(contact, "display_name", "")).strip()
        if display:
            variants.append(display)
            parts = display.split()
            if len(parts) > 1:
                variants.append(parts[-1])
        variants.extend(str(a) for a in getattr(contact, "aliases", ()))
    return normalize_contact_names(variants)


@lru_cache(maxsize=32)
def _contact_regex(names: tuple[str, ...]) -> re.Pattern[str] | None:
    if not names:
        return None
    alts: list[str] = []
    for name in sorted(names, key=len, reverse=True):
        words = []
        for word in _fold_chars(name).split(" "):
            words.append(re.escape(word[0].upper()) + "(?i:" + re.escape(word[1:]) + ")")
        alts.append(r"[ \t]+".join(words))
    return re.compile(r"(?<!\w)(?:" + "|".join(alts) + r")(?!\w)")


def _title_name_spans(text: str, stop: frozenset[str]) -> list[PiiSpan]:
    spans: list[PiiSpan] = []
    for title in _TITLE_RE.finditer(text):
        sep = _TITLE_SEP_RE.match(text, title.end())
        pos = sep.end() if sep else title.end()
        if not sep:
            continue
        first = last = -1
        for _ in range(4):
            word = _WORD_RE.match(text, pos)
            if not word or not word.group()[0].isupper() or _fold_word(word.group()) in stop:
                break
            if first < 0:
                first = word.start()
            last = word.end()
            blank = _BLANKS_RE.match(text, last)
            if not blank:
                break
            pos = blank.end()
        if first >= 0:
            spans.append(PiiSpan(first, last, "TEN", text[first:last]))
    return spans


def _uppercase_after_account_spans(text: str, stop: frozenset[str]) -> list[PiiSpan]:
    bank_words = _bank_vocab()[1] | {"bank"}
    spans: list[PiiSpan] = []
    for num in _ACCOUNT_DIGITS_RE.finditer(text):
        pos = _UPPER_SEP_RE.match(text, num.end()).end()  # type: ignore[union-attr]
        words: list[re.Match[str]] = []
        while len(words) < 5:
            word = _WORD_RE.match(text, pos)
            if not word or not word.group().isupper():
                break
            folded = _fold_word(word.group())
            if not words and folded in bank_words:  # skip leading bank alias (e.g. "MB")
                pass
            elif folded in stop:
                break
            else:
                words.append(word)
            blank = _BLANKS_RE.match(text, word.end())
            if not blank:
                break
            pos = blank.end()
        if len(words) >= 2:
            start, end = words[0].start(), words[-1].end()
            spans.append(PiiSpan(start, end, "TEN", text[start:end]))
    return spans


def detect_pii(text: str, *, contact_names: Iterable[str] | None = None) -> list[PiiSpan]:
    """Return non-overlapping PII spans (offsets into the NFC-normalised text), in order."""
    nfc = unicodedata.normalize("NFC", text)
    folded = _fold_chars(nfc)
    stop = _stop_words()
    cands: list[PiiSpan] = []

    for m in _OTP_RE.finditer(folded):
        cands.append(PiiSpan(m.start(1), m.end(1), "OTP", nfc[m.start(1) : m.end(1)]))

    for kind, regex in (("CCCD", _CCCD_RE), ("CMND", _CMND_RE), ("SDT", _SDT_RE)):
        for m in regex.finditer(nfc):
            digits = sum(ch.isdigit() for ch in m.group())
            if 6 <= digits <= 19 and _account_exempt(folded, m.start()):
                continue
            cands.append(PiiSpan(m.start(), m.end(), kind, m.group()))

    if contact_names is not None:
        regex = _contact_regex(normalize_contact_names(contact_names))
        if regex is not None:
            for m in regex.finditer(folded):
                cands.append(PiiSpan(m.start(), m.end(), "TEN", nfc[m.start() : m.end()]))

    cands.extend(_title_name_spans(nfc, stop))
    cands.extend(_uppercase_after_account_spans(nfc, stop))

    cands.sort(key=lambda s: (s.start, -(s.end - s.start)))
    result: list[PiiSpan] = []
    last_end = -1
    for span in cands:
        if span.start >= last_end:
            result.append(span)
            last_end = span.end
    return result


class Tokenizer:
    """Reversible PII redaction held in request memory only (the map is never sent anywhere)."""

    def __init__(self) -> None:
        self._mapping: dict[str, str] = {}
        self._by_value: dict[tuple[str, str], str] = {}
        self._counters: dict[str, int] = {}

    @property
    def mapping(self) -> dict[str, str]:
        return dict(self._mapping)

    def _sync(self, text: str) -> None:
        for m in _TOKEN_RE.finditer(text):
            kind, idx = m.group(1), int(m.group(2))
            if idx > self._counters.get(kind, 0):
                self._counters[kind] = idx

    def _token(self, kind: str, value: str) -> str:
        key = (kind, value)
        token = self._by_value.get(key)
        if token is None:
            self._counters[kind] = self._counters.get(kind, 0) + 1
            token = f"[{kind}_{self._counters[kind]}]"
            self._by_value[key] = token
            self._mapping[token] = value
        return token

    def redact(self, text: str, contact_names: Iterable[str] | None = None) -> tuple[str, dict[str, int]]:
        """Redact to a fixed point so that ``detect_pii`` of the result is empty."""
        names = tuple(contact_names) if contact_names is not None else None
        current = unicodedata.normalize("NFC", text)
        counts: dict[str, int] = {}
        for _ in range(_MAX_ROUNDS):
            spans = detect_pii(current, contact_names=names)
            if not spans:
                break
            self._sync(current)
            parts: list[str] = []
            pos = 0
            for span in spans:
                parts.append(current[pos : span.start])
                parts.append(self._token(span.kind, span.value))
                pos = span.end
                counts[span.kind] = counts.get(span.kind, 0) + 1
            parts.append(current[pos:])
            current = "".join(parts)
        return current, counts

    def reverse(self, text: str) -> str:
        """Replace known tokens with their original values (e.g. Planner slots)."""
        return _TOKEN_RE.sub(lambda m: self._mapping.get(m.group(0), m.group(0)), text)


def redact_pii_local(
    text: str,
    contact_names: Iterable[str] | None = None,
    tokenizer: Tokenizer | None = None,
) -> tuple[str, dict[str, int]]:
    """Return (redacted text, per-kind counts). Pass a ``Tokenizer`` to keep the reverse map."""
    return (tokenizer or Tokenizer()).redact(text, contact_names)
