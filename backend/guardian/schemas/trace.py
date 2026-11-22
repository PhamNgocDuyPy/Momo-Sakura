"""Decision trace models. ``detail`` carries only enums, numbers, booleans and domains."""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, field_validator

TraceKind = Literal["stage", "tool", "llm", "rule"]
TraceStatus = Literal["ok", "skipped", "aborted", "denied", "timeout", "error"]

_Scalar = (str, int, float, bool)


def _is_safe(value: Any) -> bool:
    if value is None or isinstance(value, _Scalar):
        return True
    if isinstance(value, dict):
        return all(isinstance(k, str) and _is_safe(v) for k, v in value.items())
    if isinstance(value, (list, tuple)):
        return all(_is_safe(v) for v in value)
    return False


class TraceStep(BaseModel):
    model_config = ConfigDict(extra="forbid")

    seq: int
    kind: TraceKind
    name: str
    t_start_ms: int
    duration_ms: int
    status: TraceStatus
    detail: dict[str, Any] = {}

    @field_validator("detail")
    @classmethod
    def _detail_scalars_only(cls, value: dict[str, Any]) -> dict[str, Any]:
        if not _is_safe(value):
            raise ValueError("trace detail must contain only scalars, lists and dicts of scalars")
        return value


class RuleFiring(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rule: str
    trigger: Literal["before_call", "after_call", "before_emit", "before_persist"]
    effect: str
    reason_code: str | None = None
    stop_code: str | None = None


class TraceRecorder:
    """Collects ``TraceStep`` entries with a monotonic, request-relative clock."""

    def __init__(self, now_ms: Callable[[], float] | None = None) -> None:
        self._now_ms: Callable[[], float] = now_ms or (lambda: time.monotonic() * 1000.0)
        self._origin = self._now_ms()
        self._steps: list[TraceStep] = []

    def elapsed_ms(self) -> int:
        return int(self._now_ms() - self._origin)

    def record(
        self,
        kind: TraceKind,
        name: str,
        status: TraceStatus = "ok",
        detail: dict[str, Any] | None = None,
        *,
        t_start_ms: int | None = None,
        duration_ms: int = 0,
    ) -> TraceStep:
        step = TraceStep(
            seq=len(self._steps) + 1,
            kind=kind,
            name=name,
            t_start_ms=self.elapsed_ms() if t_start_ms is None else t_start_ms,
            duration_ms=max(0, duration_ms),
            status=status,
            detail=detail or {},
        )
        self._steps.append(step)
        return step

    @property
    def steps(self) -> list[TraceStep]:
        return list(self._steps)

    def has(self, name: str, status: TraceStatus | None = None) -> bool:
        return any(s.name == name and (status is None or s.status == status) for s in self._steps)

    def names(self) -> list[str]:
        return [s.name for s in self._steps]
