from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

LLMProviderName = Literal["ollama", "mock", "disabled"]
RateLimitBackend = Literal["memory", "redis"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://numra:numra_dev_password@127.0.0.1:5432/numra_dev"
    environment: str = "development"

    app_timezone: str = "Europe/Berlin"

    session_secret: str = "dev-only-insecure-secret-change-me"
    allow_self_signup: bool = False
    session_cookie_name: str = "numra_session"
    session_ttl_hours: int = 24 * 14

    # Explicit provider selection is the single source of truth for which LLM
    # backend the worker uses. "disabled" (the default) means report generation
    # fails fast with a clear LLM_UNAVAILABLE error rather than silently falling
    # back to a mock. "mock" is only permitted outside production (see the
    # validator below) — it exists for local dev/CI/E2E, never for real users.
    numra_llm_provider: LLMProviderName = "disabled"
    numra_llm_max_retries: int = 3
    ollama_base_url: str | None = None
    ollama_api_key: str | None = None
    numra_llm_model_premium: str = "deepseek-v4-pro:cloud"
    numra_llm_model_fast: str = "deepseek-v4-flash:cloud"
    numra_llm_temperature: float = 0.2
    numra_llm_timeout_seconds: int = 120

    pdf_internal_token: str = "dev-only-insecure-pdf-token"
    #: Base URL of the internal PDF rendering service — used both for the truthful
    #: health check (GET {pdf_internal_url}/health/ready) and for actual export
    #: rendering dispatch (POST {pdf_internal_url}/render/report). None means "no PDF
    #: service configured" (health reports "disabled"; export creation fails with a
    #: clear error rather than attempting a request to nothing).
    pdf_internal_url: str | None = None
    pdf_render_timeout_seconds: float = 60.0

    #: Local filesystem directory export files (rendered PDFs) are written to. Only
    #: meaningful with the (only, in V1) LocalExportStorage backend.
    export_storage_dir: str = "./data/exports"

    health_check_timeout_seconds: float = 2.0
    health_ready_cache_ttl_seconds: float = 5.0

    #: "memory" (default) is a single-process, dev/test-only counter -- fine for local
    #: dev and the test suite, wrong for any multi-instance deployment (each instance
    #: would count independently, so the effective limit multiplies by instance count).
    #: Not permitted when ENVIRONMENT=production (see the validator below).
    rate_limit_backend: RateLimitBackend = "memory"
    redis_url: str = "redis://localhost:6379/0"

    log_level: str = "INFO"
    report_max_words: int = 30_000

    cors_allowed_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    request_body_max_bytes: int = 2 * 1024 * 1024

    @property
    def cookies_secure(self) -> bool:
        return self.environment == "production"

    @model_validator(mode="after")
    def _forbid_mock_llm_provider_in_production(self) -> Settings:
        if self.environment == "production" and self.numra_llm_provider == "mock":
            raise ValueError(
                "NUMRA_LLM_PROVIDER=mock is not permitted when ENVIRONMENT=production "
                "— a real user must never receive mock-generated report content. Set "
                "NUMRA_LLM_PROVIDER=ollama (with OLLAMA_BASE_URL/OLLAMA_API_KEY) or "
                "NUMRA_LLM_PROVIDER=disabled."
            )
        return self

    @model_validator(mode="after")
    def _forbid_memory_rate_limiter_in_production(self) -> Settings:
        if self.environment == "production" and self.rate_limit_backend == "memory":
            raise ValueError(
                "RATE_LIMIT_BACKEND=memory is not permitted when ENVIRONMENT=production "
                "— a multi-instance deployment needs a shared counter or each instance "
                "enforces the limit independently, multiplying the effective limit by "
                "the instance count. Set RATE_LIMIT_BACKEND=redis (with REDIS_URL)."
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
