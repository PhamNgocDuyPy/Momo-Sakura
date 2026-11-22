"""Hypothesis strategies for PII_Redactor tests (Properties 16-18)."""

from __future__ import annotations

from dataclasses import dataclass

from hypothesis import strategies as st

CONTACT_NAMES: tuple[str, ...] = ("Nguyễn Văn Minh", "Trần Thị Lan", "Lê Quốc Bảo")

# Lowercase filler: no digits, no PII keywords, no titles, no bank aliases.
_BASE_WORDS = ("chào", "hôm", "nay", "gửi", "tiền", "ăn", "trưa", "nhé", "cảm", "ơn", "rồi", "mai", "gặp")
_digits = "0123456789"


@dataclass(frozen=True)
class PiiSample:
    text: str
    digit_values: tuple[str, ...]  # original digit strings that must vanish
    names: tuple[str, ...]  # original contact names that must vanish


def _digit_str(n: int) -> st.SearchStrategy[str]:
    return st.text(alphabet=_digits, min_size=n, max_size=n)


cccd_values = _digit_str(12)
cmnd_values = _digit_str(9)
sdt_values = st.builds(lambda a, b: "0" + a + b, st.sampled_from("35789"), _digit_str(8))
otp_values = st.integers(min_value=4, max_value=8).flatmap(_digit_str)
contact_names = st.sampled_from(CONTACT_NAMES)


@st.composite
def vn_text_with_pii(draw: st.DrawFn) -> PiiSample:
    """Random Vietnamese-ish text with CCCD/CMND/SĐT/OTP/contact names inserted."""
    kinds = draw(st.lists(st.sampled_from(["CCCD", "CMND", "SDT", "OTP", "TEN"]), min_size=1, max_size=5))
    pieces: list[str] = []
    digits: list[str] = []
    names: list[str] = []

    def filler() -> list[str]:
        return draw(st.lists(st.sampled_from(_BASE_WORDS), min_size=1, max_size=4))

    pieces.extend(filler())
    for kind in kinds:
        if kind == "CCCD":
            value = draw(cccd_values)
            digits.append(value)
            pieces.append(value)
        elif kind == "CMND":
            value = draw(cmnd_values)
            digits.append(value)
            pieces.append(value)
        elif kind == "SDT":
            value = draw(sdt_values)
            digits.append(value)
            pieces.append(value)
        elif kind == "OTP":
            value = draw(otp_values)
            digits.append(value)
            pieces.extend(["otp:", value])
        else:
            name = draw(contact_names)
            names.append(name)
            pieces.append(name)
        pieces.extend(filler())
    return PiiSample(" ".join(pieces), tuple(digits), tuple(names))


account_contexts = st.sampled_from(["stk", "stk:", "số tài khoản", "so tai khoan", "tk", "tài khoản"])

# 6-19 digit account numbers, including SĐT-shaped and CCCD-shaped ones.
account_numbers = st.one_of(
    sdt_values,
    cccd_values,
    st.integers(min_value=6, max_value=19).flatmap(_digit_str),
)


@st.composite
def account_with_context(draw: st.DrawFn) -> tuple[str, str]:
    """Return (text, account number) where the number follows an account context keyword."""
    number = draw(account_numbers)
    context = draw(account_contexts)
    lead = " ".join(draw(st.lists(st.sampled_from(_BASE_WORDS), max_size=3)))
    tail = " ".join(draw(st.lists(st.sampled_from(_BASE_WORDS), max_size=3)))
    text = " ".join(part for part in (lead, context, number, tail) if part)
    return text, number
