"""POST /api/assistant/command: Trusted_Command only (typed by the user, <= 200 chars)."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from guardian.api.deps import get_container, require_session
from guardian.container import Container
from guardian.schemas.api_models import AssistantCommandRequest, AssistantCommandResponse

router = APIRouter(prefix="/api/assistant", tags=["assistant"])


@router.post("/command", response_model=AssistantCommandResponse, response_model_by_alias=True)
async def assistant_command(
    body: AssistantCommandRequest,
    session_id: str = Depends(require_session),
    container: Container = Depends(get_container),
) -> AssistantCommandResponse:
    return await container.assistant.command(session_id, body.text)
