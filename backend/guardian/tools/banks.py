"""Bank directory: BIN <-> name/alias lookup, loaded from fixtures/banks.json."""

from __future__ import annotations

import json
import os
import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


@dataclass(frozen=True)
class Bank:
    bin: str
    name: str
    aliases: tuple[str, ...]
    official_domains: tuple[str, ...]
    deeplink_template: str | None


def _fixtures_dir() -> Path:
    env = os.environ.get("FIXTURES_DIR")
    if env:
        return Path(env)
    return Path(__file__).resolve().parents[3] / "fixtures"


def fold(text: str) -> str:
    """Lowercase, strip Vietnamese diacritics, collapse whitespace."""
    decomposed = unicodedata.normalize("NFD", text.replace("đ", "d").replace("Đ", "D"))
    stripped = "".join(c for c in decomposed if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", stripped.lower()).strip()


@lru_cache(maxsize=4)
def load_banks(fixtures_dir: str | None = None) -> tuple[Bank, ...]:
    path = (Path(fixtures_dir) if fixtures_dir else _fixtures_dir()) / "banks.json"
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise RuntimeError(f"Thiếu hoặc hỏng fixture: {path.name}") from exc
    return tuple(
        Bank(
            bin=item["bin"],
            name=item["name"],
            aliases=tuple(fold(a) for a in item["aliases"]),
            official_domains=tuple(item["official_domains"]),
            deeplink_template=item.get("deeplink_template"),
        )
        for item in raw
    )


def bank_by_bin(bank_bin: str) -> Bank | None:
    return next((b for b in load_banks() if b.bin == bank_bin), None)


def bank_name(bank_bin: str) -> str | None:
    bank = bank_by_bin(bank_bin)
    return bank.name if bank else None


def bin_for_alias(alias: str) -> str | None:
    """Resolve a bank alias or name (diacritics-insensitive) to its BIN."""
    key = fold(alias)
    for bank in load_banks():
        if key == fold(bank.name) or key in bank.aliases:
            return bank.bin
    return None


def all_aliases() -> dict[str, str]:
    """Folded alias/name -> BIN, for entity scanning."""
    mapping: dict[str, str] = {}
    for bank in load_banks():
        mapping[fold(bank.name)] = bank.bin
        for alias in bank.aliases:
            mapping[alias] = bank.bin
    return mapping
