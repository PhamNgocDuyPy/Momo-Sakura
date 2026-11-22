"""Append-only audit log (``audit.jsonl``). No API to edit or delete lines (Req 29.2)."""

from __future__ import annotations

import hashlib
import json
import os
import sys
import threading
from pathlib import Path
from typing import Any, Callable


def sha256_hex(content: str | bytes) -> str:
    data = content.encode("utf-8") if isinstance(content, str) else content
    return hashlib.sha256(data).hexdigest()


def apply_consent(
    record: dict[str, Any],
    *,
    explicit_consent_flag: bool,
    original: str | bytes | None,
    redacted_text: str | None,
) -> dict[str, Any]:
    """Fill ``content_sha256`` / ``evidence_redacted`` per consent (Req 29.3, 29.4).

    Without consent only the hash is kept. With consent only the already-redacted text is kept;
    the original content is never written.
    """
    out = dict(record)
    out["explicit_consent_flag"] = explicit_consent_flag
    out["content_sha256"] = sha256_hex(original) if original is not None else None
    out["evidence_redacted"] = redacted_text if explicit_consent_flag else None
    return out


class AuditLog:
    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._lock = threading.Lock()
        self._degraded = False

    @property
    def degraded(self) -> bool:
        return self._degraded

    @property
    def health(self) -> str:
        return "degraded" if self._degraded else "ok"

    def append(self, record: dict[str, Any]) -> bool:
        """Append one JSON line. Never raises; returns False and marks degraded on OSError."""
        try:
            line = json.dumps(record, ensure_ascii=False, default=_json_default)
            with self._lock:
                self._path.parent.mkdir(parents=True, exist_ok=True)
                with open(self._path, "a", encoding="utf-8", newline="\n") as fh:
                    fh.write(line + "\n")
                    fh.flush()
                    os.fsync(fh.fileno())
            self._degraded = False
            return True
        except OSError as exc:
            self._degraded = True
            print(f"audit write failed: {exc}", file=sys.stderr)
            return False


def _json_default(value: Any) -> Any:
    iso: Callable[[], str] | None = getattr(value, "isoformat", None)
    if iso is not None:
        return iso()
    name = getattr(value, "name", None)
    if isinstance(name, str):
        return name
    raise TypeError(f"not JSON serializable: {type(value).__name__}")
