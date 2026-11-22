"""Circuit breaker around LLM calls (Req 17.6, design.md "CircuitBreaker").

Every call is wrapped in ``asyncio.wait_for`` with ``LLM_TIMEOUT_MS``. After
``failure_threshold`` consecutive timeouts/errors the breaker opens for ``open_seconds``:
calls are skipped (``status="SKIPPED"``, ``breaker="open"``) so the caller goes straight to
its fallback. Once the window elapses a single trial call is allowed (half-open); success
closes the breaker, failure re-opens it.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Generic, Literal, TypeVar

from guardian.llm.base import LLMResult

T = TypeVar("T")

BreakerState = Literal["closed", "open", "half_open"]
BreakerStatus = Literal["OK", "TIMEOUT", "ERROR", "SKIPPED"]


@dataclass(frozen=True)
class BreakerOutcome(Generic[T]):
    status: BreakerStatus
    result: LLMResult[T] | None
    breaker: BreakerState  # state the call was admitted under ("open" when skipped)
    latency_ms: int
    error: str | None = None  # exception class name, never a message (may hold user data)


class CircuitBreaker:
    def __init__(
        self,
        timeout_ms: int = 4000,
        failure_threshold: int = 3,
        open_seconds: float = 60.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._timeout_s = timeout_ms / 1000
        self._threshold = failure_threshold
        self._open_seconds = open_seconds
        self._clock = clock
        self._failures = 0
        self._opened_at: float | None = None
        self._probe_in_flight = False

    @property
    def state(self) -> BreakerState:
        if self._opened_at is None:
            return "closed"
        if self._clock() - self._opened_at >= self._open_seconds:
            return "half_open"
        return "open"

    def _skipped(self) -> BreakerOutcome[T]:
        return BreakerOutcome("SKIPPED", None, "open", 0)

    async def call(self, fn: Callable[[], Awaitable[LLMResult[T]]]) -> BreakerOutcome[T]:
        state = self.state
        if state == "open":
            return self._skipped()
        if state == "half_open":
            if self._probe_in_flight:
                return self._skipped()
            self._probe_in_flight = True

        started = self._clock()
        try:
            result = await asyncio.wait_for(fn(), timeout=self._timeout_s)
        except asyncio.TimeoutError:
            self._record_failure()
            return BreakerOutcome("TIMEOUT", None, state, self._elapsed_ms(started))
        except Exception as exc:  # noqa: BLE001 - any provider failure counts
            self._record_failure()
            return BreakerOutcome("ERROR", None, state, self._elapsed_ms(started), type(exc).__name__)
        finally:
            if state == "half_open":
                self._probe_in_flight = False

        if result.status in ("ERROR", "NOT_IMPLEMENTED"):
            self._record_failure()
            return BreakerOutcome("ERROR", result, state, self._elapsed_ms(started))
        self._record_success()
        return BreakerOutcome("OK", result, state, self._elapsed_ms(started))

    def _elapsed_ms(self, started: float) -> int:
        return max(0, int((self._clock() - started) * 1000))

    def _record_success(self) -> None:
        self._failures = 0
        self._opened_at = None

    def _record_failure(self) -> None:
        self._failures += 1
        if self._failures >= self._threshold or self._opened_at is not None:
            # Threshold reached, or a half-open trial failed: (re)open the window.
            self._opened_at = self._clock()
