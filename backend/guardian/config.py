"""Application settings loaded from environment / .env."""

from __future__ import annotations

import sys
from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

VERSION = "0.1.0"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # LLM
    llm_provider: Literal["mock", "anthropic", "bedrock", "openai_compat"] = "mock"
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-5"
    openai_compat_base_url: str = ""
    openai_compat_api_key: SecretStr = SecretStr("")  # repr/str hide the value
    openai_compat_model: str = ""
    openai_compat_json_mode: Literal["json_schema", "tools", "json_object"] = "json_schema"
    llm_timeout_ms: int = Field(default=4000, gt=0)
    mock_llm_delay_ms: int = Field(default=0, ge=0)
    # Security / session
    session_hash_secret: str = "change-me-local-only"
    guardian_debug: bool = False
    # Data
    fixtures_dir: str = "../fixtures"
    sandbox_now: str = "2026-11-30T20:00:00+07:00"
    audit_log_path: str = "./var/audit.jsonl"
    risk_memory_ttl_hours: int = Field(default=24, gt=0)
    # Thresholds
    fan_in_velocity_threshold: int = Field(default=10, gt=0)
    prefilter_soft_threshold: float = Field(default=0.85, ge=0.0, le=1.0)
    # Optional integrations
    google_safe_browsing_api_key: str = ""
    momo_hotline: str = "1900545441"
    cors_origins: str = ""

    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


def validate_startup(settings: Settings) -> None:
    """Fail fast on invalid configuration (exit code 2)."""
    if settings.llm_provider == "anthropic" and not settings.anthropic_api_key.strip():
        print(
            "Thiếu biến môi trường ANTHROPIC_API_KEY (LLM_PROVIDER=anthropic)",
            file=sys.stderr,
        )
        sys.exit(2)
    if settings.llm_provider == "openai_compat":
        missing = [
            name
            for name, value in (
                ("OPENAI_COMPAT_BASE_URL", settings.openai_compat_base_url),
                ("OPENAI_COMPAT_API_KEY", settings.openai_compat_api_key.get_secret_value()),
                ("OPENAI_COMPAT_MODEL", settings.openai_compat_model),
            )
            if not value.strip()
        ]
        if missing:
            print(
                f"Thiếu biến môi trường {', '.join(missing)} (LLM_PROVIDER=openai_compat)",
                file=sys.stderr,
            )
            sys.exit(2)
        if not settings.openai_compat_base_url.strip().lower().startswith(("http://", "https://")):
            print(
                "OPENAI_COMPAT_BASE_URL phải bắt đầu bằng http:// hoặc https://",
                file=sys.stderr,
            )
            sys.exit(2)
