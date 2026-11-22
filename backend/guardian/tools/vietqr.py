"""VietQR (EMVCo / NAPAS 247) verifier and encoder. Deterministic, no I/O, no LLM.

`verify_vietqr_emvco` never raises: any unexpected input maps to INVALID_FORMAT.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any

from guardian.schemas.enums import QrFlag, QrResult
from guardian.tools.banks import bank_by_bin, bank_name

NAPAS_AID = "A000000727"
DEFAULT_SERVICE_CODE = "QRIBFTTA"
MAX_PAYLOAD_CHARS = 4096
_FOREIGN_AID_MARKERS = ("A000000677", "SG.PAYNOW", "ID.CO.QRIS.WWW")

_PAYLOAD_RE = re.compile(r"^.*6304[0-9A-Fa-f]{4}$", re.DOTALL)
_AMOUNT_RE = re.compile(r"^[0-9]{1,13}$")
_BIN_RE = re.compile(r"^[0-9]{6}$")
_ACCOUNT_RE = re.compile(r"^[0-9]{6,19}$")
_SERVICE_RE = re.compile(r"^[A-Z0-9]{1,20}$")

Tlv = list[tuple[str, str]]


# ---------------------------------------------------------------- CRC


def crc16_ccitt_false(data: bytes | str) -> int:
    """CRC-16/CCITT-FALSE: poly 0x1021, init 0xFFFF, no reflection, xorout 0."""
    raw = data.encode("utf-8") if isinstance(data, str) else data
    crc = 0xFFFF
    for byte in raw:
        crc ^= byte << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xFFFF if crc & 0x8000 else (crc << 1) & 0xFFFF
    return crc


# ---------------------------------------------------------------- TLV


def _split(seq: str | bytes) -> list[tuple[str, str | bytes]] | None:
    """Split a TLV sequence that must be consumed exactly; None on any malformation."""
    items: list[tuple[str, str | bytes]] = []
    i, n = 0, len(seq)
    while i < n:
        if i + 4 > n:
            return None
        head = seq[i : i + 4]
        if isinstance(head, bytes):
            try:
                head_s = head.decode("ascii")
            except UnicodeDecodeError:
                return None
        else:
            head_s = head
        tag, length_s = head_s[:2], head_s[2:]
        if not (head_s.isascii() and tag.isdigit() and length_s.isdigit()):
            return None
        length = int(length_s)
        value = seq[i + 4 : i + 4 + length]
        if len(value) != length:
            return None
        items.append((tag, value))
        i += 4 + length
    return items


def _parse_level(text: str, byte_mode: bool) -> Tlv | None:
    """Parse one TLV level, with lengths counted in code points or in UTF-8 bytes."""
    items = _split(text.encode("utf-8") if byte_mode else text)
    if items is None:
        return None
    out: Tlv = []
    for tag, value in items:
        if isinstance(value, bytes):
            try:
                value = value.decode("utf-8")
            except UnicodeDecodeError:
                return None
        out.append((tag, value))
    return out


@dataclass
class ParsedTlv:
    top: Tlv
    nested: dict[str, Tlv] = field(default_factory=dict)
    byte_fallback: bool = False


def _parse_mode(payload: str, byte_mode: bool) -> ParsedTlv | None:
    top = _parse_level(payload, byte_mode)
    if not top:
        return None
    last_tag, last_value = top[-1]
    if last_tag != "63" or len(last_value) != 4:
        return None
    tags = [t for t, _ in top]
    if len(set(tags)) != len(tags):
        return None
    parsed = ParsedTlv(top=top, byte_fallback=byte_mode)
    for tag, value in top:
        if tag == "62" or 26 <= int(tag) <= 51:
            sub = _parse_level(value, byte_mode)
            if sub is None:
                if tag in ("38", "62"):
                    return None
                continue
            parsed.nested[tag] = sub
    return parsed


def parse_tlv(payload: str) -> ParsedTlv | None:
    """Parse by code point first, then by UTF-8 byte length (flagged `byte_fallback`).

    The byte-length result is accepted only when the TLV ends exactly at Tag 63.
    """
    try:
        return _parse_mode(payload, False) or _parse_mode(payload, True)
    except Exception:
        return None


# ---------------------------------------------------------------- verifier


@dataclass
class QrVerification:
    result: QrResult
    flags: list[QrFlag] = field(default_factory=list)
    fields: dict[str, Any] | None = None
    crc: dict[str, str] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "result": self.result.value,
            "flags": [f.value for f in self.flags],
            "fields": self.fields,
            "crc": self.crc,
        }


def _first(items: Tlv | None, tag: str) -> str | None:
    for t, v in items or []:
        if t == tag:
            return v
    return None


def verify_vietqr_emvco(payload_raw: str) -> QrVerification:
    """Verify a VietQR payload (design steps 1-7). Never raises."""
    try:
        return _verify(payload_raw)
    except Exception:
        return QrVerification(QrResult.INVALID_FORMAT)


def _verify(payload: object) -> QrVerification:
    invalid = QrVerification(QrResult.INVALID_FORMAT)
    if not isinstance(payload, str) or len(payload) > MAX_PAYLOAD_CHARS:
        return invalid
    # 1. shape
    if not _PAYLOAD_RE.match(payload):
        return invalid
    # 2. CRC before any parsing
    expected = payload[-4:].upper()
    try:
        computed = f"{crc16_ccitt_false(payload[:-4]):04X}"
    except UnicodeEncodeError:
        return invalid
    crc = {"expected": expected, "computed": computed}
    if expected != computed:
        return QrVerification(QrResult.BAD_CRC, crc=crc)
    # 3. TLV
    parsed = parse_tlv(payload)
    if parsed is None:
        return QrVerification(QrResult.INVALID_FORMAT, crc=crc)
    flags: list[QrFlag] = [QrFlag.UTF8_BYTE_FALLBACK] if parsed.byte_fallback else []
    top = parsed.top
    byte_mode = parsed.byte_fallback
    tag38 = parsed.nested.get("38")
    tag62 = parsed.nested.get("62")

    # 4. foreign / non-VND
    foreign = any(
        26 <= int(t) <= 51 and any(m in v.upper() for m in _FOREIGN_AID_MARKERS) for t, v in top
    )
    currency, country = _first(top, "53"), _first(top, "58")
    if (currency is not None and currency != "704") or (country is not None and country != "VN"):
        foreign = True
    fields = _build_fields(parsed, byte_mode)
    if foreign:
        return QrVerification(QrResult.FOREIGN_OR_NON_VND, flags, fields, crc)

    # 5. mandatory structure
    def bad() -> QrVerification:
        return QrVerification(QrResult.INVALID_FORMAT, flags, fields, crc)

    if any(_first(top, t) is None for t in ("00", "01", "38", "53", "58", "63")):
        return bad()
    if _first(top, "00") != "01" or _first(top, "01") not in ("11", "12"):
        return bad()
    if _first(tag38, "00") != NAPAS_AID:
        return bad()
    sub01 = _first(tag38, "01")
    beneficiary = _parse_level(sub01, byte_mode) if sub01 is not None else None
    if not beneficiary or not _first(beneficiary, "00") or not _first(beneficiary, "01"):
        return bad()
    amount = _first(top, "54")
    if amount is not None and not _AMOUNT_RE.match(amount):
        return bad()
    # 6. legacy service code
    if _first(tag38, "02") is None:
        flags.append(QrFlag.LEGACY_DEFAULT_SERVICE_CODE)
    # 7. tag 62 is returned as data only (already in fields)
    _ = tag62
    return QrVerification(QrResult.VALID_VIETQR, flags, fields, crc)


def _build_fields(parsed: ParsedTlv, byte_mode: bool) -> dict[str, Any]:
    top, tag38, tag62 = parsed.top, parsed.nested.get("38"), parsed.nested.get("62")
    sub01 = _first(tag38, "01")
    beneficiary = (_parse_level(sub01, byte_mode) if sub01 is not None else None) or []
    bank_bin = _first(beneficiary, "00")
    amount = _first(top, "54")
    return {
        "payload_format": _first(top, "00"),
        "poi_method": _first(top, "01"),
        "aid": _first(tag38, "00"),
        "bank_bin": bank_bin,
        "bank_name": bank_name(bank_bin) if bank_bin else None,
        "account_number": _first(beneficiary, "01"),
        "service_code": (_first(tag38, "02") or DEFAULT_SERVICE_CODE) if tag38 else None,
        "amount_vnd": int(amount) if amount is not None and _AMOUNT_RE.match(amount) else None,
        "currency": _first(top, "53"),
        "country": _first(top, "58"),
        "tag62": {
            "purpose": _first(tag62, "08"),
            "bill_number": _first(tag62, "01"),
            "reference": _first(tag62, "05"),
        },
    }


# ---------------------------------------------------------------- encoder


def _tlv(tag: str, value: str) -> str:
    if len(value) > 99:
        raise ValueError(f"tag {tag} longer than 99 code points")
    return f"{tag}{len(value):02d}{value}"


def _has_control(text: str) -> bool:
    return any(unicodedata.category(c) in ("Cc", "Cs") for c in text)


def encode_vietqr(
    bin: str,  # noqa: A002 - name fixed by the design
    account: str,
    amount_vnd: int | None,
    memo: str,
    poi: str = "12",
    *,
    service_code: str = DEFAULT_SERVICE_CODE,
) -> str:
    """Build a VietQR payload (tags 00 01 38 53 54? 58 62? 63). Raises ValueError on bad input."""
    if not _BIN_RE.match(bin) or bank_by_bin(bin) is None:
        raise ValueError("unknown bank BIN")
    if not _ACCOUNT_RE.match(account):
        raise ValueError("account number must be 6-19 digits")
    if amount_vnd is not None and (
        isinstance(amount_vnd, bool) or not isinstance(amount_vnd, int) or not 0 <= amount_vnd < 10**13
    ):
        raise ValueError("amount must be an integer in [0, 10^13)")
    if len(memo) > 25 or _has_control(memo):
        raise ValueError("memo must be at most 25 code points without control characters")
    if poi not in ("11", "12"):
        raise ValueError("poi must be 11 or 12")
    if not _SERVICE_RE.match(service_code):
        raise ValueError("invalid service code")

    beneficiary = _tlv("00", bin) + _tlv("01", account)
    tag38 = _tlv("00", NAPAS_AID) + _tlv("01", beneficiary) + _tlv("02", service_code)
    body = _tlv("00", "01") + _tlv("01", poi) + _tlv("38", tag38) + _tlv("53", "704")
    if amount_vnd is not None:
        body += _tlv("54", str(amount_vnd))
    body += _tlv("58", "VN")
    if memo:
        body += _tlv("62", _tlv("08", memo))
    body += "6304"
    return f"{body}{crc16_ccitt_false(body):04X}"


def fold_ascii(memo: str) -> str:
    """Strip Vietnamese diacritics and drop remaining non-ASCII / control characters."""
    text = memo.replace("đ", "d").replace("Đ", "D")
    decomposed = unicodedata.normalize("NFD", text)
    stripped = "".join(c for c in decomposed if unicodedata.category(c) != "Mn")
    return "".join(c for c in stripped if c.isascii() and c.isprintable())
