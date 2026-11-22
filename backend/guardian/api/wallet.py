"""GET /api/wallet/summary."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from guardian.api.deps import get_container, require_session
from guardian.container import Container
from guardian.features.wallet_summary import WalletSummary, build_wallet_summary

router = APIRouter(prefix="/api/wallet", tags=["wallet"])


@router.get("/summary", response_model=WalletSummary)
async def wallet_summary(
    session_id: str = Depends(require_session),
    container: Container = Depends(get_container),
) -> WalletSummary:
    return build_wallet_summary(
        container.wallet_provider,
        container.sandbox_clock.now(),
        container.shield_stats.get(session_id),
    )
