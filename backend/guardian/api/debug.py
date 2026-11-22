"""Debug-only endpoints (404 when ``GUARDIAN_DEBUG`` is off)."""

from __future__ import annotations

import time

from fastapi import APIRouter, Depends

from guardian.api.deps import GuardianError, get_container, require_session
from guardian.container import Container
from guardian.schemas.api_models import DebugExtractRequest, DebugExtractResponse
from guardian.tools.pii import contact_name_variants, redact_pii_local

router = APIRouter(prefix="/api/debug", tags=["debug"])


@router.post("/extract", response_model=DebugExtractResponse)
async def debug_extract(
    body: DebugExtractRequest,
    _session_id: str = Depends(require_session),
    container: Container = Depends(get_container),
) -> DebugExtractResponse:
    if not container.settings.guardian_debug:
        raise GuardianError(404, "NOT_FOUND", "")
    started = time.perf_counter()
    names = contact_name_variants(container.wallet_provider.contacts())
    redacted, _counts = redact_pii_local(body.text, names)
    result = await container.llm.extract(redacted, body.mode)
    return DebugExtractResponse(
        redacted_text=redacted,
        llm_status=result.status,
        extraction=result.value.model_dump(mode="json") if result.value is not None else None,
        latency_ms=int((time.perf_counter() - started) * 1000),
    )
