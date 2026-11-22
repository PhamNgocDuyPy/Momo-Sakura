"""Simulated transfer commit: enforces tier and cooldown on the server."""

from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, Depends

from guardian.api.deps import GuardianError, get_container, require_session
from guardian.container import Container
from guardian.policy.templates_vi import ERRORS
from guardian.schemas.api_models import TransferCommitRequest, TransferCommitResponse
from guardian.schemas.enums import DecisionTier

router = APIRouter(prefix="/api/transfer", tags=["transfer"])


@router.post("/commit", response_model=TransferCommitResponse)
async def transfer_commit(
    body: TransferCommitRequest,
    session_id: str = Depends(require_session),
    container: Container = Depends(get_container),
) -> TransferCommitResponse:
    record = container.verdict_store.get(body.verdict_id, session_id)
    if record is None:
        raise GuardianError(404, "VERDICT_NOT_FOUND", ERRORS["VERDICT_NOT_FOUND"])
    if record.tier == DecisionTier.HARD_HOLD:
        raise GuardianError(
            403, "TRANSFER_BLOCKED_HARD_HOLD", ERRORS["TRANSFER_BLOCKED_HARD_HOLD"]
        )
    if record.tier == DecisionTier.SOFT_FRICTION:
        cooling = record.floors.cooling_off_seconds()
        elapsed = container.system_clock.now() - record.created_at
        needed_questions = int(record.extra.get("question_count", 0))
        if (
            not body.cooldown_completed
            or elapsed < timedelta(seconds=cooling)
            or body.answered_questions < needed_questions
        ):
            raise GuardianError(409, "COOLDOWN_NOT_FINISHED", ERRORS["COOLDOWN_NOT_FINISHED"])
    tx = record.tx
    if tx.bin is None or tx.account is None or tx.amount is None:
        raise GuardianError(409, "VERDICT_NOT_FOUND", ERRORS["VERDICT_NOT_FOUND"])
    container.ledger.add(session_id, tx.bin, tx.account, tx.amount)
    container.verdict_store.mark_cooldown_completed(record.verdict_id)
    return TransferCommitResponse(ledger_total_24h_vnd=container.ledger.total_24h(session_id))
