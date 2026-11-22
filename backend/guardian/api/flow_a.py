"""Flow A endpoints. ``POST /api/flow-a/check`` is rule-based and never calls an LLM."""

from __future__ import annotations

import sys

from fastapi import APIRouter, Depends

from guardian.api.deps import GuardianError, get_container, require_session
from guardian.container import Container
from guardian.control_plane.flow_a import (
    ContextNotApplicable,
    FastUnblockNotAllowed,
    IdentityCheckFailed,
    VerdictNotFound,
)
from guardian.control_plane.tool_runner import ToolNotAllowed
from guardian.policy.composer import ComposerInvalid
from guardian.policy.templates_vi import ERRORS
from guardian.schemas.api_models import (
    CheckResponse,
    ContextRequest,
    FastUnblockRequest,
    FlowACheckRequest,
)

router = APIRouter(prefix="/api/flow-a", tags=["flow-a"])


@router.post("/check", response_model=CheckResponse)
async def flow_a_check(
    body: FlowACheckRequest,
    session_id: str = Depends(require_session),
    container: Container = Depends(get_container),
) -> CheckResponse:
    if body.debug is not None and not container.settings.guardian_debug:
        raise GuardianError(403, "DEBUG_DISABLED", "Chức năng gỡ lỗi đang tắt.")
    try:
        result = await container.flow_a.check(session_id, body)
    except ComposerInvalid as exc:
        container.audit.append({"error": ComposerInvalid.error_code, "channel": "FLOW_A"})
        raise GuardianError(500, ComposerInvalid.error_code, ERRORS["COMPOSER_INVALID"]) from exc
    except ToolNotAllowed as exc:
        container.audit.append({"error": "TOOL_NOT_ALLOWED", "channel": "FLOW_A"})
        raise GuardianError(500, "TOOL_NOT_ALLOWED", ERRORS["TOOL_NOT_ALLOWED"]) from exc
    except GuardianError:
        raise
    except Exception as exc:  # unexpected: never leak details to the client
        print(f"flow_a error: {type(exc).__name__}", file=sys.stderr)
        container.audit.append({"error": "FLOW_A_ERROR", "channel": "FLOW_A"})
        raise GuardianError(500, "FLOW_A_ERROR", ERRORS["FLOW_A_ERROR"]) from exc
    return result.response


@router.post("/fast-unblock", response_model=CheckResponse)
async def flow_a_fast_unblock(
    body: FastUnblockRequest,
    session_id: str = Depends(require_session),
    container: Container = Depends(get_container),
) -> CheckResponse:
    try:
        return container.flow_a.fast_unblock(session_id, body)
    except IdentityCheckFailed as exc:
        raise GuardianError(400, "IDENTITY_CHECK_FAILED", ERRORS["IDENTITY_CHECK_FAILED"]) from exc
    except VerdictNotFound as exc:
        raise GuardianError(404, "VERDICT_NOT_FOUND", ERRORS["VERDICT_NOT_FOUND"]) from exc
    except FastUnblockNotAllowed as exc:
        raise GuardianError(
            409, "FAST_UNBLOCK_NOT_ALLOWED", ERRORS["FAST_UNBLOCK_NOT_ALLOWED"]
        ) from exc
    except ComposerInvalid as exc:
        raise GuardianError(500, ComposerInvalid.error_code, ERRORS["COMPOSER_INVALID"]) from exc


@router.post("/context", response_model=CheckResponse)
async def flow_a_context(
    body: ContextRequest,
    session_id: str = Depends(require_session),
    container: Container = Depends(get_container),
) -> CheckResponse:
    try:
        return container.flow_a.apply_context(session_id, body)
    except VerdictNotFound as exc:
        raise GuardianError(404, "VERDICT_NOT_FOUND", ERRORS["VERDICT_NOT_FOUND"]) from exc
    except ContextNotApplicable as exc:
        raise GuardianError(
            409, "CONTEXT_NOT_APPLICABLE", ERRORS["CONTEXT_NOT_APPLICABLE"]
        ) from exc
    except ComposerInvalid as exc:
        raise GuardianError(500, ComposerInvalid.error_code, ERRORS["COMPOSER_INVALID"]) from exc
