"""Session id validation, payer session hash and the per-request context."""

from __future__ import annotations

import hashlib
import hmac
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from guardian.policy.floors import FloorSet
from guardian.schemas.api_models import Channel, DebugOverrides
from guardian.schemas.enums import SourceIntegrity, StopCode
from guardian.schemas.trace import RuleFiring, TraceRecorder


def validate_session_id(value: str | None) -> str:
    """Return the canonical uuid v4 string or raise ``ValueError``."""
    if value:
        try:
            parsed = uuid.UUID(value)
        except ValueError:
            parsed = None
        if parsed is not None and parsed.version == 4 and str(parsed) == value.lower():
            return str(parsed)
    raise ValueError("session id must be a uuid v4")


def payer_session_hash(secret: str, session_id: str) -> str:
    """HMAC-SHA256(secret, session_id) as hex, truncated to 32 characters."""
    digest = hmac.new(secret.encode("utf-8"), session_id.encode("utf-8"), hashlib.sha256)
    return digest.hexdigest()[:32]


@dataclass
class RequestContext:
    request_id: str
    session_id: str
    payer_session_hash: str
    channel: Channel
    floors: FloorSet = field(default_factory=FloorSet)
    trace: TraceRecorder = field(default_factory=TraceRecorder)
    rules_fired: list[RuleFiring] = field(default_factory=list)
    stop_codes: list[StopCode] = field(default_factory=list)
    source_integrity: SourceIntegrity | None = None
    qr_present: bool = False
    explicit_consent_flag: bool = False
    client_time: datetime | None = None
    debug: DebugOverrides | None = None

    @classmethod
    def create(
        cls,
        session_id: str,
        channel: Channel,
        secret: str,
        *,
        request_id: str | None = None,
        **kwargs: Any,
    ) -> RequestContext:
        sid = validate_session_id(session_id)
        return cls(
            request_id=request_id or str(uuid.uuid4()),
            session_id=sid,
            payer_session_hash=payer_session_hash(secret, sid),
            channel=channel,
            **kwargs,
        )
