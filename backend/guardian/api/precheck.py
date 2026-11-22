"""POST /api/precheck: local-only PII redaction, CPU prefilter, URL flags and hijack check."""

from __future__ import annotations

import time

from fastapi import APIRouter, Depends

from guardian.api.deps import get_container, require_session
from guardian.container import Container
from guardian.schemas.api_models import PrecheckRequest, PrecheckResponse, UrlReport
from guardian.tools.hijack import detect_hijack
from guardian.tools.pii import contact_name_variants, redact_pii_local
from guardian.tools.prefilter import prompt_guard_cpu_score
from guardian.tools.url_checker import check_urls

router = APIRouter(prefix="/api", tags=["precheck"])


@router.post("/precheck", response_model=PrecheckResponse)
async def precheck(
    body: PrecheckRequest,
    _session_id: str = Depends(require_session),
    container: Container = Depends(get_container),
) -> PrecheckResponse:
    started = time.perf_counter()
    names = contact_name_variants(container.wallet_provider.contacts())
    redacted, counts = redact_pii_local(body.text, contact_names=names)
    urls = [UrlReport(domain=u.domain, flags=sorted(u.flags)) for u in check_urls(body.text)]
    return PrecheckResponse(
        redacted_text=redacted,
        redaction_counts=counts,
        prompt_guard_cpu_score=prompt_guard_cpu_score(body.text),
        urls=urls,
        hijack_detected=detect_hijack(body.text),
        duration_ms=int((time.perf_counter() - started) * 1000),
    )
