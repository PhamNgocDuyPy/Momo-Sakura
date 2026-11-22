"""POST /api/qr/verify: deterministic VietQR (EMVCo) verification, no LLM."""

from __future__ import annotations

import uuid
from typing import Any
from urllib.parse import quote

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field

from guardian.api.deps import GuardianError, get_container, require_session
from guardian.container import Container
from guardian.control_plane.session import payer_session_hash
from guardian.policy.templates_vi import ERRORS
from guardian.schemas.api_models import QrEncodeRequest, QrEncodeResponse, QrEncodeVerify
from guardian.schemas.enums import DecisionTier, QrResult
from guardian.tools.banks import bank_by_bin
from guardian.tools.vietqr import encode_vietqr, fold_ascii, verify_vietqr_emvco

router = APIRouter(prefix="/api/qr", tags=["qr"])


class QrVerifyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    payload: str = Field(max_length=512)


class QrVerifyResponse(BaseModel):
    result: str
    flags: list[str]
    fields: dict[str, Any] | None
    crc: dict[str, str] | None


def _deeplink(template: str | None, payload: str, req: QrEncodeRequest, memo: str) -> str | None:
    if template is None:
        return None
    values = {
        "bin": req.bank_bin,
        "account": req.account_number,
        "amount": "" if req.amount_vnd is None else str(req.amount_vnd),
        "memo": memo,
        "payload": payload,
    }
    out = template
    for key, value in values.items():
        out = out.replace("{" + key + "}", quote(value, safe=""))
    return out


def _deny_handoff(container: Container, session_id: str, req: QrEncodeRequest, reason: str) -> None:
    container.audit.append(
        {
            "ts": container.system_clock.now().isoformat(),
            "audit_id": f"au_{uuid.uuid4().hex[:16]}",
            "channel": "BANK_HANDOFF",
            "event": "HANDOFF_DENIED",
            "session_hash": payer_session_hash(container.settings.session_hash_secret, session_id),
            "verdict_id": req.verdict_id,
            "reason": reason,
            "extra": {"purpose": req.purpose},
        }
    )


@router.post("/encode", response_model=QrEncodeResponse)
async def qr_encode(
    body: QrEncodeRequest,
    session_id: str = Depends(require_session),
    container: Container = Depends(get_container),
) -> QrEncodeResponse:
    if body.purpose == "BANK_HANDOFF":
        record = (
            container.verdict_store.get(body.verdict_id, session_id) if body.verdict_id else None
        )
        # Unknown verdicts are treated like HARD_HOLD: never export a QR without a verdict.
        if record is None or record.tier == DecisionTier.HARD_HOLD:
            reason = "VERDICT_NOT_FOUND" if record is None else "HARD_HOLD"
            _deny_handoff(container, session_id, body, reason)
            raise GuardianError(
                403, "HANDOFF_BLOCKED_HARD_HOLD", ERRORS["HANDOFF_BLOCKED_HARD_HOLD"]
            )
        if record.tier == DecisionTier.SOFT_FRICTION and not record.cooldown_completed:
            raise GuardianError(409, "COOLDOWN_NOT_FINISHED", ERRORS["COOLDOWN_NOT_FINISHED"])

    memo = fold_ascii(body.memo)
    try:
        payload = encode_vietqr(body.bank_bin, body.account_number, body.amount_vnd, memo)
    except ValueError as exc:
        raise GuardianError(422, "VALIDATION_ERROR", ERRORS["VALIDATION_ERROR"]) from exc
    verification = verify_vietqr_emvco(payload)
    if verification.result is not QrResult.VALID_VIETQR:
        container.audit.append({"error": "ENCODER_SELF_CHECK_FAILED", "channel": "QR_ENCODE"})
        raise GuardianError(
            500, "ENCODER_SELF_CHECK_FAILED", ERRORS["ENCODER_SELF_CHECK_FAILED"]
        )
    bank = bank_by_bin(body.bank_bin)
    return QrEncodeResponse(
        payload=payload,
        verify=QrEncodeVerify(result=verification.result),
        deeplink=_deeplink(bank.deeplink_template if bank else None, payload, body, memo),
    )


@router.post("/verify", response_model=QrVerifyResponse)
async def qr_verify(
    body: QrVerifyRequest,
    _session_id: str = Depends(require_session),
) -> QrVerifyResponse:
    return QrVerifyResponse(**verify_vietqr_emvco(body.payload).to_dict())
