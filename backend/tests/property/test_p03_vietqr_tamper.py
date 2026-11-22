"""Property 3: Phát hiện sửa đổi QR.

**Validates: Requirements 4.3, 5.5**
"""

from __future__ import annotations

import string

from hypothesis import given
from hypothesis import strategies as st

from guardian.schemas.enums import QrResult
from guardian.tools.vietqr import encode_vietqr, verify_vietqr_emvco
from tests.property.strategies.vietqr import vietqr_fields

_PRINTABLE = string.printable[:-5]  # printable ASCII without whitespace control chars


@st.composite
def tampered(draw: st.DrawFn) -> tuple[str, str]:
    payload = encode_vietqr(**draw(vietqr_fields()))
    limit = len(payload) - 8  # index of the final "6304"
    i = draw(st.integers(min_value=0, max_value=limit - 1))
    new = draw(st.sampled_from(_PRINTABLE).filter(lambda c: c != payload[i]))
    return payload, payload[:i] + new + payload[i + 1 :]


# Feature: momo-guardian-web, Property 3: For any encoder payload and any position before 6304, replacing one ASCII char makes verify return non-VALID_VIETQR
@given(tampered())
def test_single_char_tamper_is_detected(pair: tuple[str, str]) -> None:
    original, mutated = pair
    assert verify_vietqr_emvco(original).result is QrResult.VALID_VIETQR
    assert mutated.endswith(original[-8:])  # still ends with 6304XXXX
    assert verify_vietqr_emvco(mutated).result is QrResult.BAD_CRC
