"""Bill_Splitter (F3): integer-only, deterministic. Shares always sum to the allocated total."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal, Protocol

MAX_PARTICIPANTS = 20
MAX_ITEMS = 30


class _Item(Protocol):
    quantity: int
    unit_price_vnd: int


class _Assignment(Protocol):
    item_index: int
    participant_ids: Sequence[str]


class SplitInputError(ValueError):
    """Raised for structurally invalid split input. `code` is an ERRORS key."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class SplitOutcome:
    status: Literal["OK", "TOTAL_MISMATCH"]
    items_sum_vnd: int
    mismatch_vnd: int
    shares: dict[str, int]


def items_sum(items: Sequence[_Item]) -> int:
    return sum(i.quantity * i.unit_price_vnd for i in items)


def split_equal(total: int, participants: Sequence[str]) -> dict[str, int]:
    """Equal split; the remainder goes one VND each to the first participants in list order."""
    q, r = divmod(total, len(participants))
    return {p: q + (1 if i < r else 0) for i, p in enumerate(participants)}


def split_by_item(
    items: Sequence[_Item],
    assignments: Sequence[_Assignment],
    participants: Sequence[str],
) -> dict[str, int]:
    """Split each line equally among its assignees (fixed participant order)."""
    shares = {p: 0 for p in participants}
    order = {p: i for i, p in enumerate(participants)}
    for a in assignments:
        item = items[a.item_index]
        line_total = item.quantity * item.unit_price_vnd
        assignees = sorted(set(a.participant_ids), key=order.__getitem__)
        for p, amt in split_equal(line_total, assignees).items():
            shares[p] += amt
    return shares


def compute_split(
    items: Sequence[_Item],
    receipt_total: int,
    participants: Sequence[str],
    mode: Literal["EQUAL", "BY_ITEM"],
    assignments: Sequence[_Assignment] | None,
) -> SplitOutcome:
    """Validate and split. Raises SplitInputError (VALIDATION_ERROR / UNASSIGNED_ITEMS)."""
    if not 1 <= len(participants) <= MAX_PARTICIPANTS or not 1 <= len(items) <= MAX_ITEMS:
        raise SplitInputError("VALIDATION_ERROR")
    if len(set(participants)) != len(participants):
        raise SplitInputError("VALIDATION_ERROR")
    total_items = items_sum(items)
    if total_items != receipt_total:
        return SplitOutcome("TOTAL_MISMATCH", total_items, abs(total_items - receipt_total), {})

    if mode == "EQUAL":
        return SplitOutcome("OK", total_items, 0, split_equal(receipt_total, participants))

    known = set(participants)
    seen: set[int] = set()
    for a in assignments or []:
        if (
            not 0 <= a.item_index < len(items)
            or a.item_index in seen
            or not set(a.participant_ids) <= known
        ):
            raise SplitInputError("VALIDATION_ERROR")
        seen.add(a.item_index)
    if seen != set(range(len(items))):
        raise SplitInputError("UNASSIGNED_ITEMS")
    return SplitOutcome(
        "OK", total_items, 0, split_by_item(items, assignments or [], participants)
    )
