"""Hypothesis strategies for VietQR encode/verify tests."""

from __future__ import annotations

from typing import Any

from hypothesis import strategies as st

from guardian.tools.banks import load_banks

valid_bins = st.sampled_from(sorted({b.bin for b in load_banks()}))
accounts = st.text(alphabet="0123456789", min_size=6, max_size=19)
amounts = st.one_of(st.none(), st.integers(min_value=0, max_value=10**13 - 1))

_VIETNAMESE = "àáảãạăắằẳẵặâấầẩẫậèéẻẽẹêếềểễệìíỉĩịòóỏõọôốồổỗộơớờởỡợùúủũụưứừửữựỳýỷỹỵđĐ"
_EMOJI = "😀🎉🧧🌸❤️"

# Non-empty memo (an empty memo omits Tag 62 and is covered by unit tests).
memos = st.text(
    alphabet=st.one_of(
        st.characters(blacklist_categories=("Cc", "Cs")),
        st.sampled_from(_VIETNAMESE + _EMOJI + " "),
    ),
    min_size=1,
    max_size=25,
)


@st.composite
def vietqr_fields(draw: st.DrawFn) -> dict[str, Any]:
    """Keyword arguments for `encode_vietqr` (bin, account, amount_vnd, memo, poi)."""
    return {
        "bin": draw(valid_bins),
        "account": draw(accounts),
        "amount_vnd": draw(amounts),
        "memo": draw(memos),
        "poi": draw(st.sampled_from(["11", "12"])),
    }
