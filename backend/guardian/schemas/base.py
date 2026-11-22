"""Base Pydantic models shared by the schema modules."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class Strict(BaseModel):
    """Immutable model that rejects unknown keys at every nesting level (LLM output, verdicts)."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=False)


class ApiModel(BaseModel):
    """Request/response model that rejects unknown keys."""

    model_config = ConfigDict(extra="forbid")
