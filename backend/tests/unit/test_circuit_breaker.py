import asyncio

from guardian.llm.base import LLMResult
from guardian.llm.circuit_breaker import CircuitBreaker


class Clock:
    def __init__(self) -> None:
        self.t = 1000.0

    def __call__(self) -> float:
        return self.t


def _ok() -> LLMResult[int]:
    return LLMResult(1, "OK", "end_turn", 1)


async def _good() -> LLMResult[int]:
    return _ok()


async def _slow() -> LLMResult[int]:
    await asyncio.sleep(1)
    return _ok()


async def _boom() -> LLMResult[int]:
    raise RuntimeError("secret user text")


async def test_timeout_then_open_skips_calls() -> None:
    clock = Clock()
    cb = CircuitBreaker(timeout_ms=10, clock=clock)
    for _ in range(3):
        out = await cb.call(_slow)
        assert out.status == "TIMEOUT"
    assert cb.state == "open"
    out = await cb.call(_good)
    assert out.status == "SKIPPED" and out.breaker == "open" and out.result is None


async def test_half_open_success_closes() -> None:
    clock = Clock()
    cb = CircuitBreaker(timeout_ms=50, clock=clock)
    for _ in range(3):
        await cb.call(_boom)
    clock.t += 60
    assert cb.state == "half_open"
    out = await cb.call(_good)
    assert out.status == "OK" and out.breaker == "half_open"
    assert cb.state == "closed"


async def test_half_open_failure_reopens_and_error_hides_message() -> None:
    clock = Clock()
    cb = CircuitBreaker(timeout_ms=50, clock=clock)
    for _ in range(3):
        await cb.call(_boom)
    clock.t += 61
    out = await cb.call(_boom)
    assert out.status == "ERROR" and out.error == "RuntimeError"
    assert cb.state == "open"


async def test_success_resets_consecutive_count() -> None:
    cb = CircuitBreaker(timeout_ms=50, clock=Clock())
    await cb.call(_boom)
    await cb.call(_boom)
    await cb.call(_good)
    await cb.call(_boom)
    await cb.call(_boom)
    assert cb.state == "closed"


async def test_only_one_probe_in_half_open() -> None:
    clock = Clock()
    cb = CircuitBreaker(timeout_ms=500, clock=clock)
    for _ in range(3):
        await cb.call(_boom)
    clock.t += 60

    async def slow_ok() -> LLMResult[int]:
        await asyncio.sleep(0.05)
        return _ok()

    first, second = await asyncio.gather(cb.call(slow_ok), cb.call(_good))
    assert {first.status, second.status} == {"OK", "SKIPPED"}
