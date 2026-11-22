"""Hypothesis strategies for receipts and bill-split inputs."""

from __future__ import annotations

from dataclasses import dataclass

from hypothesis import strategies as st

from guardian.schemas.api_models import SplitAssignment, SplitItem


@dataclass(frozen=True)
class Receipt:
    items: list[SplitItem]
    participants: list[str]
    assignments: list[SplitAssignment]

    @property
    def total(self) -> int:
        return sum(i.quantity * i.unit_price_vnd for i in self.items)


@st.composite
def receipts(draw: st.DrawFn, max_items: int = 30, max_people: int = 20) -> Receipt:
    """Receipt with 1-30 items, 1-20 participants and an assignment covering every item."""
    n_people = draw(st.integers(1, max_people))
    people = [f"p{i + 1}" for i in range(n_people)]
    n_items = draw(st.integers(1, max_items))
    items = [
        SplitItem(
            name=f"mon {i}",
            quantity=draw(st.integers(1, 99)),
            unit_price_vnd=draw(st.integers(0, 5_000_000)),
        )
        for i in range(n_items)
    ]
    assignments = [
        SplitAssignment(
            item_index=i,
            participant_ids=draw(st.lists(st.sampled_from(people), min_size=1, max_size=n_people)),
        )
        for i in range(n_items)
    ]
    return Receipt(items=items, participants=people, assignments=assignments)
