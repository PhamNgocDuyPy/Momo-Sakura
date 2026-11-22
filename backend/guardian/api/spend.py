"""POST /api/spend/query: F6 spending questions over the sandbox wallet (deterministic, no LLM)."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from guardian.api.deps import get_container, require_session
from guardian.container import Container
from guardian.features.spend_query import compute
from guardian.schemas.api_models import SpendQueryRequest, SpendQueryResponse
from guardian.schemas.planner import SpendSlots

router = APIRouter(prefix="/api/spend", tags=["spend"])


@router.post("/query", response_model=SpendQueryResponse, response_model_by_alias=True)
async def spend_query(
    body: SpendQueryRequest,
    _session_id: str = Depends(require_session),
    container: Container = Depends(get_container),
) -> SpendQueryResponse:
    slots = SpendSlots(category=body.category, period=body.period, metric=body.metric)
    return compute(container.wallet_provider.transactions(), slots, container.sandbox_clock.now())
