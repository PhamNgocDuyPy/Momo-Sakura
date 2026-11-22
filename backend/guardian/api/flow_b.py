"""Flow B endpoint: ``POST /api/flow-b/check`` (NDJSON stream by default, JSON with stream=false)."""

from __future__ import annotations

import asyncio
import sys
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from pydantic import ValidationError

from guardian.api.deps import GuardianError, get_container, require_session
from guardian.container import Container
from guardian.control_plane.flow_b import FlowBResult
from guardian.policy.templates_vi import ERRORS
from guardian.schemas.api_models import (
    CheckResponse,
    FlowBCheckRequest,
    FlowBFinalEvent,
    FlowBStage2Event,
)

router = APIRouter(prefix="/api/flow-b", tags=["flow-b"])

MAX_TEXT = 4000
MAX_QR = 512
_DONE = object()


def _validation_error(details: dict[str, Any] | None = None) -> GuardianError:
    return GuardianError(422, "VALIDATION_ERROR", ERRORS["VALIDATION_ERROR"], details)


def _parse_request(raw: Any) -> FlowBCheckRequest:
    content = raw.get("content") if isinstance(raw, dict) else None
    if isinstance(content, dict):
        text, qr = content.get("text"), content.get("qr_payload")
        if isinstance(text, str) and len(text) > MAX_TEXT:
            raise GuardianError(422, "CONTENT_TOO_LONG", ERRORS["CONTENT_TOO_LONG"])
        if isinstance(qr, str) and len(qr) > MAX_QR:
            raise _validation_error({"field": "content.qr_payload"})
        if not (isinstance(text, str) and text.strip()) and not (isinstance(qr, str) and qr):
            raise _validation_error({"field": "content"})
    try:
        return FlowBCheckRequest.model_validate(raw)
    except ValidationError as exc:
        raise _validation_error({"fields": [".".join(map(str, e["loc"])) for e in exc.errors()]}) from exc


@router.post("/check")
async def flow_b_check(
    request: Request,
    stream: bool = True,
    session_id: str = Depends(require_session),
    container: Container = Depends(get_container),
) -> Any:
    try:
        raw = await request.json()
    except ValueError as exc:
        raise _validation_error() from exc
    body = _parse_request(raw)
    if body.debug is not None and not container.settings.guardian_debug:
        raise GuardianError(403, "DEBUG_DISABLED", ERRORS["DEBUG_DISABLED"])

    if not stream:
        result = await _run(container, session_id, body, None)
        return result.response

    queue: asyncio.Queue[Any] = asyncio.Queue()

    async def on_stage2(event: FlowBStage2Event) -> None:
        await queue.put(event)

    async def worker() -> None:
        try:
            result = await _run(container, session_id, body, on_stage2)
            await queue.put(FlowBFinalEvent(response=result.response))
        except Exception as exc:  # noqa: BLE001
            print(f"flow_b error: {type(exc).__name__}", file=sys.stderr)
        finally:
            await queue.put(_DONE)

    async def events() -> AsyncIterator[str]:
        task = asyncio.ensure_future(worker())
        try:
            while True:
                item = await queue.get()
                if item is _DONE:
                    break
                yield item.model_dump_json() + "\n"
        finally:
            if not task.done():
                task.cancel()

    return StreamingResponse(events(), media_type="application/x-ndjson")


async def _run(
    container: Container,
    session_id: str,
    body: FlowBCheckRequest,
    on_stage2: Any,
) -> FlowBResult:
    try:
        return await container.flow_b.check(session_id, body, on_stage2=on_stage2)
    except Exception as exc:  # check() already falls back; this is a last resort
        print(f"flow_b error: {type(exc).__name__}", file=sys.stderr)
        container.audit.append({"error": "FLOW_B_ERROR", "channel": "FLOW_B"})
        raise GuardianError(500, "FLOW_B_ERROR", ERRORS["FLOW_A_ERROR"]) from exc
