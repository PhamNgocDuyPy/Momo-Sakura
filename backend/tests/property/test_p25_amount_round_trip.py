"""Property 25: Round trip định dạng số tiền.

**Validates: Requirements 16.9, 19.6, 19.7**
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from hypothesis import given

from guardian.tools.amount import format_vnd, parse_amount
from tests.property.strategies.amount import vnd_amounts

_VECTORS = Path(__file__).resolve().parents[3] / "fixtures" / "amount_vectors.json"
_PATTERN = re.compile(r"^\d{1,3}(\.\d{3})* đ$")


@given(vnd_amounts)
def test_format_vnd_round_trip(n: int) -> None:
    text = format_vnd(n)
    assert _PATTERN.match(text), text
    assert parse_amount(text) == n


def test_format_vnd_matches_fixture_vectors() -> None:
    entries = json.loads(_VECTORS.read_text(encoding="utf-8"))["format"]
    assert entries
    for entry in entries:
        assert format_vnd(entry["n"]) == entry["text"]
