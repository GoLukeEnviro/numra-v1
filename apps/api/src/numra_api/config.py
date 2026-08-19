from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://numra:numra_dev_password@127.0.0.1:5432/numra_dev"
    environment: str = "development"

    app_timezone: str = "Europe/Berlin"

    session_secret: str = "dev-only-insecure-secret-change-me"
    allow_self_signup: bool = False
    session_cookie_name: str = "numra_session"
    session_ttl_hours: int = 24 * 14

    numra_llm_enabled: bool = False
    ollama_base_url: str | None = None
    ollama_api_key: str | None = None
    numra_llm_model_premium: str = "deepseek-v4-pro:cloud"
    numra_llm_model_fast: str = "deepseek-v4-flash:cloud"
    numra_llm_temperature: float = 0.2
    numra_llm_timeout_seconds: int = 120

    pdf_internal_token: str = "dev-only-insecure-pdf-token"

    log_level: str = "INFO"
    report_max_words: int = 30_000

    cors_allowed_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    request_body_max_bytes: int = 2 * 1024 * 1024

    @property
    def cookies_secure(self) -> bool:
        return self.environment == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
