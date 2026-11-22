from __future__ import annotations

from fastapi import APIRouter, Depends

from fastapi import Request

from guardian.api.deps import get_container, get_settings_dep
from guardian.config import VERSION, Settings

router = APIRouter()


def _llm_model(settings: Settings) -> str | None:
    if settings.llm_provider == "anthropic":
        return settings.anthropic_model
    if settings.llm_provider == "openai_compat":
        return settings.openai_compat_model
    return None


@router.get("/api/health")
async def health(
    request: Request, settings: Settings = Depends(get_settings_dep)
) -> dict[str, object]:
    return {
        "audit": get_container(request).audit.health,
        "status": "ok",
        "llm_provider": settings.llm_provider,
        "llm_model": _llm_model(settings),
        "version": VERSION,
        "sandbox_now": settings.sandbox_now,
        "debug": settings.guardian_debug,
    }
