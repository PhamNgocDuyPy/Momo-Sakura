"""Contact resolution for F2 (assistant transfer commands). Pure over the contact list.

A contact matches a query (diacritics-insensitive) when the query equals the full name, the given
name (last word), one of the aliases, or any run of consecutive words of the full name.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Literal

from guardian.providers.base import Contact

MatchStatus = Literal["RESOLVED", "AMBIGUOUS", "NOT_FOUND"]

_NON_WORD_RE = re.compile(r"[^\w]+", re.UNICODE)


def fold_words(text: str) -> tuple[str, ...]:
    """Lowercase, strip diacritics (đ -> d) and split into words; punctuation is dropped."""
    text = text.replace("đ", "d").replace("Đ", "D")
    decomposed = unicodedata.normalize("NFD", text)
    stripped = "".join(c for c in decomposed if unicodedata.category(c) != "Mn").lower()
    return tuple(w for w in _NON_WORD_RE.split(stripped) if w)


@dataclass(frozen=True)
class ContactMatch:
    status: MatchStatus
    candidates: tuple[Contact, ...] = ()

    @property
    def contact(self) -> Contact | None:
        return self.candidates[0] if self.status == "RESOLVED" else None


def _contains_run(haystack: Sequence[str], needle: Sequence[str]) -> bool:
    n = len(needle)
    return any(tuple(haystack[i : i + n]) == tuple(needle) for i in range(len(haystack) - n + 1))


def _matches(query: tuple[str, ...], contact: Contact) -> bool:
    name = fold_words(contact.display_name)
    if _contains_run(name, query):  # covers full name, given name (last word) and word runs
        return True
    return any(fold_words(alias) == query for alias in contact.aliases)


def match(query: str, contacts: Iterable[Contact]) -> ContactMatch:
    """Resolve ``query`` against ``contacts``: 1 hit RESOLVED, 2+ AMBIGUOUS, 0 NOT_FOUND."""
    words = fold_words(query)
    if not words:
        return ContactMatch("NOT_FOUND")
    hits = tuple(c for c in contacts if _matches(words, c))
    if not hits:
        return ContactMatch("NOT_FOUND")
    return ContactMatch("RESOLVED" if len(hits) == 1 else "AMBIGUOUS", hits)
