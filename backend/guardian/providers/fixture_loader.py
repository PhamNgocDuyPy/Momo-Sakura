"""Shared fixture loading for sandbox providers. Only `providers/` reads `fixtures/`."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_REPO_FIXTURES = Path(__file__).resolve().parents[3] / "fixtures"


class FixtureError(RuntimeError):
    """Raised at startup when a required fixture is missing or corrupt."""


def resolve_fixtures_dir(configured: str) -> Path:
    path = Path(configured)
    if path.is_dir():
        return path
    return _REPO_FIXTURES


def load_json(fixtures_dir: Path, name: str) -> Any:
    try:
        return json.loads((fixtures_dir / name).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise FixtureError(f"Thiếu hoặc hỏng fixture: {name}") from exc
