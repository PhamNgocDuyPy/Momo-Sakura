"""POST /api/split/compute: bill splitting with per-person VietQR codes (no LLM)."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from guardian.api.deps import GuardianError, get_container, require_session
from guardian.container import Container
from guardian.features.bill_splitter import SplitInputError, compute_split
from guardian.policy.templates_vi import ERRORS
from guardian.schemas.api_models import SplitComputeRequest, SplitComputeResponse, SplitShare
from guardian.schemas.enums import QrResult
from guardian.tools.vietqr import encode_vietqr, fold_ascii, verify_vietqr_emvco

router = APIRouter(prefix="/api/split", tags=["split"])


def _qr_for(bank_bin: str, account: str, amount: int, memo: str) -> tuple[str | None, str]:
    """Encode then self-check; anything but VALID_VIETQR becomes QR_ERROR."""
    try:
        payload = encode_vietqr(bank_bin, account, amount, fold_ascii(memo))
    except ValueError:
        return None, "QR_ERROR"
    if verify_vietqr_emvco(payload).result is not QrResult.VALID_VIETQR:
        return None, "QR_ERROR"
    return payload, "VALID_VIETQR"


@router.post("/compute", response_model=SplitComputeResponse)
async def split_compute(
    body: SplitComputeRequest,
    _session_id: str = Depends(require_session),
    container: Container = Depends(get_container),
) -> SplitComputeResponse:
    ids = [p.id for p in body.participants]
    try:
        outcome = compute_split(
            body.items, body.receipt_total_vnd, ids, body.mode, body.assignments
        )
    except SplitInputError as exc:
        raise GuardianError(422, exc.code, ERRORS[exc.code]) from exc
    if outcome.status == "TOTAL_MISMATCH":
        return SplitComputeResponse(
            status="TOTAL_MISMATCH",
            total_vnd=body.receipt_total_vnd,
            items_sum_vnd=outcome.items_sum_vnd,
            mismatch_vnd=outcome.mismatch_vnd,
            shares=[],
        )

    profile = container.wallet_provider.profile()
    payee_id = ids[0]  # payee SELF is the first participant ("Bạn")
    shares: list[SplitShare] = []
    for pid in ids:
        amount = outcome.shares[pid]
        if pid == payee_id:
            shares.append(
                SplitShare(
                    participant_id=pid,
                    amount_vnd=amount,
                    is_payee=True,
                    qr_payload=None,
                    qr_status="SKIPPED_PAYEE",
                )
            )
            continue
        payload, status = _qr_for(profile.bank_bin, profile.account_number, amount, body.memo)
        shares.append(
            SplitShare(
                participant_id=pid,
                amount_vnd=amount,
                is_payee=False,
                qr_payload=payload,
                qr_status=status,  # type: ignore[arg-type]
            )
        )
    return SplitComputeResponse(
        status="OK",
        total_vnd=body.receipt_total_vnd,
        items_sum_vnd=outcome.items_sum_vnd,
        mismatch_vnd=0,
        shares=shares,
    )
