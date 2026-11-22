"""Hypothesis strategies for Risk_Memory operation sequences."""

from __future__ import annotations

from hypothesis import strategies as st

from guardian.reason_codes import REGISTRY

_HARD_CODES = sorted(c for c, s in REGISTRY.items() if s.min_tier.name == "HARD_HOLD")
_SESSIONS = ["s1", "s2"]
_BINS = ["970436", "970415", None]
_DIGITS = st.sampled_from(["0071000999888", "1903777888999", "0123456789"])
_DOMAINS = st.sampled_from(["evil.example", "scam.vn"])


def risk_memory_keys() -> st.SearchStrategy[str]:
    acct = st.builds(
        lambda b, d: f"acct:{b or '*'}:{d}", st.sampled_from(_BINS), _DIGITS
    )
    dom = _DOMAINS.map(lambda d: f"dom:{d}")
    return st.one_of(acct, dom)


def risk_memory_ops() -> st.SearchStrategy[list[tuple]]:
    """Sequence of ("write", session, key, code) | ("advance", seconds) | ("lookup", session, key)."""
    write = st.tuples(
        st.just("write"),
        st.sampled_from(_SESSIONS),
        risk_memory_keys(),
        st.sampled_from(_HARD_CODES),
    )
    advance = st.tuples(st.just("advance"), st.integers(min_value=0, max_value=20 * 3600))
    lookup = st.tuples(st.just("lookup"), st.sampled_from(_SESSIONS), risk_memory_keys())
    return st.lists(st.one_of(write, advance, lookup), max_size=40)
