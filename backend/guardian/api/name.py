"""Name confirmation endpoints (R2 two-step OCR confirmation, D4 confirmation token)."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from guardian.api.deps import GuardianError, get_container, require_session
from guardian.container import Container
from guardian.policy.templates_vi import ERRORS
from guardian.schemas.api_models import (
    NameConfirmRequest,
    NameConfirmResponse,
    NameInquiryRequest,
    NameInquiryResponse,
)
from guardian.schemas.enums import SourceIntegrity
from guardian.tools.banks import bank_name

router = APIRouter(prefix="/api/name", tags=["name"])


def _not_found() -> GuardianError:
    return GuardianError(404, "PENDING_NOT_FOUND", ERRORS["PENDING_NOT_FOUND"])


@router.post("/inquiry", response_model=NameInquiryResponse)
async def name_inquiry(
    body: NameInquiryRequest,
    session_id: str = Depends(require_session),
    container: Container = Depends(get_container),
) -> NameInquiryResponse:
    pending = container.pending_confirm.get(body.pending_id, session_id)
    if pending is None:
        raise _not_found()
    result = await container.risk_provider.name_inquiry(body.bank_bin, body.account_number)
    container.pending_confirm.update(
        body.pending_id, bin=body.bank_bin, account=body.account_number, status="PENDING"
    )
    return NameInquiryResponse(
        pending_id=body.pending_id,
        display_name=result.display_name,
        bank_name=result.bank_name or bank_name(body.bank_bin),
        account_digits_spaced=" ".join(body.account_number),
        found=result.found,
        sandbox=result.sandbox,
    )


@router.post("/confirm", response_model=NameConfirmResponse)
async def name_confirm(
    body: NameConfirmRequest,
    session_id: str = Depends(require_session),
    container: Container = Depends(get_container),
) -> NameConfirmResponse:
    pending = container.pending_confirm.get(body.pending_id, session_id)
    if pending is None:
        raise _not_found()
    if not body.confirmed:
        return NameConfirmResponse(source_integrity=SourceIntegrity.OCR_UNCONFIRMED)
    token = container.pending_confirm.issue_token(session_id, pending.bin, pending.account)
    result = await container.flow_b.reevaluate_confirmed(session_id, body.pending_id)
    if result is None:
        raise _not_found()
    return NameConfirmResponse(
        confirmation_token=token,
        source_integrity=SourceIntegrity.OCR_CONFIRMED_BY_USER,
        check=result.response,
    )
