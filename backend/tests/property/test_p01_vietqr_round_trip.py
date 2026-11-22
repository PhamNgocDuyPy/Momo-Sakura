"""Property 1: VietQR encode -> verify round trip.

**Validates: Requirements 4.1, 4.2, 4.7, 5.1, 5.2, 5.3**
"""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from guardian.schemas.enums import QrFlag, QrResult
from guardian.tools.vietqr import crc16_ccitt_false, encode_vietqr, verify_vietqr_emvco
from tests.property.strategies.vietqr import accounts, amounts, memos, valid_bins


# Feature: momo-guardian-web, Property 1: VietQR encode -> verify round trip
@given(
    bin=valid_bins,
    account=accounts,
    amount=amounts,
    memo=st.one_of(st.just(""), memos),
    poi=st.sampled_from(["11", "12"]),
)
def test_encode_verify_round_trip(
    bin: str, account: str, amount: int | None, memo: str, poi: str  # noqa: A002
) -> None:
    payload = encode_vietqr(bin, account, amount, memo, poi)
    res = verify_vietqr_emvco(payload)

    assert res.result == QrResult.VALID_VIETQR
    assert QrFlag.UTF8_BYTE_FALLBACK not in res.flags
    assert res.crc is not None and res.crc["expected"] == res.crc["computed"]
    assert res.crc["computed"] == f"{crc16_ccitt_false(payload[:-4]):04X}"

    f = res.fields
    assert f is not None
    assert f["currency"] == "704"
    assert f["country"] == "VN"
    assert f["poi_method"] == poi
    assert f["bank_bin"] == bin
    assert f["account_number"] == account
    assert f["amount_vnd"] == amount
    assert f["tag62"]["purpose"] == (memo or None)
