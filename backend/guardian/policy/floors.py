"""Floors: deterministic minimum tiers. The final tier is the max over all floors.

``FloorSet`` is append-only. The only ways to lower the tier are the two explicit user-driven
operations ``remove_removable("FAST_UNBLOCK")`` and ``remove_removable("CONTEXT_IN_STORE")``;
the LLM never has access to either.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from typing import Literal

from guardian.reason_codes import REGISTRY
from guardian.schemas.enums import DecisionTier, HardSource

__all__ = [
    "DecisionTier",
    "Floor",
    "FloorRule",
    "FloorSet",
    "HardSource",
    "RemovalReason",
    "FAST_UNBLOCK_SOURCES",
]

FloorRule = Literal[
    "R1", "R2", "R3", "R4", "R5", "R6", "TIER1", "URL", "MEMORY",
    "PLAYBOOK", "CUE", "F4", "F5", "COLD_START", "CONTEXT", "FAST_UNBLOCK",
    "LLM_FALLBACK", "BASELINE",
]  # fmt: skip
RemovalReason = Literal["FAST_UNBLOCK", "CONTEXT_IN_STORE"]

# HARD sources that a user may clear with identity verification (Fast Unblock).
FAST_UNBLOCK_SOURCES: frozenset[HardSource] = frozenset(
    {HardSource.GNN_MULE, HardSource.FAN_IN_VELOCITY}
)


@dataclass(frozen=True)
class Floor:
    tier: DecisionTier
    reason_code: str
    rule: FloorRule
    hard_source: HardSource | None = None
    removable_by: frozenset[RemovalReason] = frozenset()

    def __post_init__(self) -> None:
        if self.reason_code not in REGISTRY:
            raise ValueError(f"reason code not in registry: {self.reason_code}")
        if self.tier == DecisionTier.HARD_HOLD and self.hard_source is None:
            raise ValueError("HARD_HOLD floor requires a hard_source")


class FloorSet:
    """Append-only collection of floors."""

    def __init__(self, floors: Iterable[Floor] = ()) -> None:
        self._floors: list[Floor] = []
        for floor in floors:
            self.add(floor)

    def add(self, floor: Floor) -> None:
        self._floors.append(floor)

    def __iter__(self) -> Iterator[Floor]:
        return iter(self._floors)

    def __len__(self) -> int:
        return len(self._floors)

    @property
    def floors(self) -> tuple[Floor, ...]:
        return tuple(self._floors)

    @property
    def final_tier(self) -> DecisionTier:
        return max((f.tier for f in self._floors), default=DecisionTier.ALLOW)

    def allow_fast_unblock(self) -> bool:
        """True when the tier is HARD_HOLD and every HARD floor is a clearable source."""
        if self.final_tier != DecisionTier.HARD_HOLD:
            return False
        return all(
            f.hard_source in FAST_UNBLOCK_SOURCES
            for f in self._floors
            if f.tier == DecisionTier.HARD_HOLD
        )

    def cooling_off_seconds(self) -> int:
        return max((REGISTRY[f.reason_code].cooling_off for f in self._floors), default=0)

    def remove_removable(self, by: RemovalReason) -> list[Floor]:
        """Drop floors whose ``removable_by`` contains ``by``; return the removed floors."""
        removed = [f for f in self._floors if by in f.removable_by]
        self._floors = [f for f in self._floors if by not in f.removable_by]
        return removed
