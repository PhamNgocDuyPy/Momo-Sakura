"""Hypothesis strategies for Amount_Parser / Amount_Formatter tests."""

from __future__ import annotations

from hypothesis import strategies as st

# Non-negative VND amounts, biased toward grouping boundaries.
vnd_amounts = st.one_of(
    st.integers(min_value=0, max_value=10**12),
    st.sampled_from([0, 999, 1000, 999_999, 1_000_000, 9_000_000, 10_000_000, 20_000_000]),
)

unit_a = st.integers(min_value=0, max_value=999)
digits_b = st.text(alphabet="0123456789", min_size=1, max_size=3)


@st.composite
def slang_amounts(draw: st.DrawFn) -> tuple[str, int]:
    """Return (text, expected VND) following the Property 26 formulas."""
    a = draw(unit_a)
    kind = draw(st.sampled_from(["k", "tr", "tr_b", "dot_tr", "lit", "xi", "cu"]))
    if kind == "k":
        return f"{a}k", a * 1000
    if kind == "tr":
        return f"{a}tr", a * 1_000_000
    if kind == "lit":
        return f"{a} lít", a * 100_000
    if kind == "xi":
        return f"{a} xị", a * 100_000
    if kind == "cu":
        return f"{a} củ", a * 1_000_000
    b = draw(digits_b)
    value = a * 1_000_000 + int(b) * 10 ** (6 - len(b))
    if kind == "tr_b":
        return f"{a}tr{b}", value
    return f"{a}.{b}tr", value


# Random letters/symbols that must never parse (no digits, so no grammar match).
garbage_text = st.text(
    alphabet=st.characters(blacklist_categories=("Cs", "Nd"), blacklist_characters="\x00"),
    max_size=20,
).filter(lambda s: not any(ch.isdigit() for ch in s))
