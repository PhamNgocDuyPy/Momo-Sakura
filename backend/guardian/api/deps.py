"""Shared request dependencies: session header and debug gate."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import Header, Request

from guardian.config import Settings
from guardian.container import Container


class GuardianError(Exception):
    """API error rendered as {"error", "message_vi", "details"}."""

    def __init__(
        self,
        status_code: int,
        error: str,
        message_vi: str = "",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(error)
        self.status_code = status_code
        self.error = error
        self.message_vi = message_vi
        self.details = details or {}


def get_container(request: Request) -> Container:
    return request.app.state.container  # type: ignore[no-any-return]


def get_settings_dep(request: Request) -> Settings:
    return get_container(request).settings


def parse_session_id(value: str | None) -> str:
    """Return canonical uuid v4 string or raise SESSION_REQUIRED."""
    if value:
        try:
            parsed = uuid.UUID(value)
        except ValueError:
            parsed = None
        if parsed is not None and parsed.version == 4 and str(parsed) == value.lower():
            return str(parsed)
    raise GuardianError(
        400, "SESSION_REQUIRED", "Thiếu hoặc sai mã phiên. Vui lòng tải lại trang."
    )


def require_session(
    x_guardian_session: str | None = Header(default=None),
) -> str:
    return parse_session_id(x_guardian_session)


def require_debug(request: Request) -> None:
    """Gate for debug-only features."""
    if not get_settings_dep(request).guardian_debug:
        raise GuardianError(
            403, "DEBUG_DISABLED", "Chức năng gỡ lỗi đang tắt."
        )
