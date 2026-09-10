from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

LLMProviderName = Literal["ollama", "mock", "disabled"]
RateLimitBackend = Literal["memory", "redis"]
EmailBackend = Literal["logging", "disabled", "smtp"]


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
    #: Generous enough to cover the PDF service's own one-time Chromium cold start
    #: (lazily launched on its first request, see apps/pdf/src/server.js) landing
    #: inside the same request this client is waiting on, not just steady-state
    #: render time -- verified via a real docker-compose-e2e run where the previous
    #: 60s default was reliably exceeded under genuine multi-container CI load.
    pdf_render_timeout_seconds: float = 120.0

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

    #: Deliberately a Settings field (unlike routes/public.py's former APP_NAME
    #: constant) -- branding is not a security-relevant value like
    #: `allow_self_signup`, so letting a deployment configure it carries none of the
    #: risk that letting one configure e.g. session/CSRF behavior would.
    app_brand_name: str = "AVENYTH"

    #: "logging" (default) only logs the email instead of sending it -- fine for local
    #: dev/CI/E2E, never for real users; not permitted when ENVIRONMENT=production (see
    #: the validator below). "disabled" is the `numra_llm_provider="disabled"` analogue:
    #: no real send mechanism exists in V1 (see email/sender.py), so it is what a
    #: production deployment configures today -- request-email-verification/
    #: forgot-password fail fast and legibly rather than one of them being silently
    #: mislabeled "sent". Same three-way shape as `numra_llm_provider`.
    email_backend: EmailBackend = "logging"
    #: Base URL of the web app that connection-invitation redeem links, verify-email
    #: links, and reset-password links all point to -- see `build_web_app_url()`
    #: below, the single place that joins this with a path (trailing slash on this
    #: value is tolerated, see that method). This is also the "PUBLIC_APP_BASE_URL"
    #: the SMTP mail templates build absolute links from -- it already is exactly
    #: that (a public, absolute app base URL), so the SMTP work reuses it instead of
    #: introducing a second, duplicate setting. Default matches the real local
    #: Next.js dev/prod port (apps/web, see docker-compose.yml's `web` service and
    #: `cors_allowed_origins` above) -- not Vite's 5173, which this app does not use.
    web_app_base_url: str = "http://localhost:3000"
    email_verification_token_ttl_hours: int = 24
    password_reset_token_ttl_minutes: int = 60

    #: The "smtp" `EmailBackend` -- a real provider (see email/smtp_sender.py). All
    #: fields below are only meaningful when `email_backend="smtp"`; `None`/defaults
    #: elsewhere are harmless. `smtp_password` is a `SecretStr` so it can never be
    #: logged or `repr()`-ed in plaintext (see `_require_smtp_config_in_production`
    #: and `email/smtp_sender.py` for the one place `.get_secret_value()` is called).
    smtp_host: str | None = None
    smtp_port: int | None = None
    smtp_username: str | None = None
    smtp_password: SecretStr | None = None
    smtp_from_email: str | None = None
    smtp_from_name: str | None = None
    #: STARTTLS upgrade on a plaintext connection (typically port 587) -- the common
    #: default for most providers.
    smtp_starttls: bool = True
    #: Implicit TLS from the first byte (typically port 465). Mutually exclusive with
    #: `smtp_starttls` -- see `_forbid_conflicting_smtp_tls_modes`.
    smtp_use_tls: bool = False
    smtp_timeout_seconds: float = 10.0

    #: AVENYTH V2 rollout flags (specs/v2/architecture.md "Feature flags"). Alle Default
    #: False in JEDER Umgebung -- explizites Opt-in ueberall noetig, nicht nur in
    #: Production. avenyth_v2_enabled ist der Master-Switch; die anderen 6 sind UND-
    #: verknuepft damit, nie unabhaengig ausreichend.
    avenyth_v2_enabled: bool = False
    avenyth_connections_enabled: bool = False
    avenyth_relationship_workspaces_enabled: bool = False
    avenyth_checkins_enabled: bool = False
    avenyth_tasks_enabled: bool = False
    avenyth_copilot_enabled: bool = False
    avenyth_evidence_layer_enabled: bool = False

    @property
    def cookies_secure(self) -> bool:
        return self.environment == "production"

    def build_web_app_url(self, path: str) -> str:
        """Joins `web_app_base_url` with `path`, tolerating a trailing slash on the
        base and/or a leading slash on the path -- the single place invitation
        redeem links (routes/connections.py) and verify-email/reset-password links
        (services/auth_recovery_service.py) build their absolute URL, so all three
        stay consistent without duplicating the join logic. Never derived from
        request Host/Forwarded headers -- always this explicit setting."""
        return f"{self.web_app_base_url.rstrip('/')}/{path.lstrip('/')}"

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
    def _forbid_logging_email_backend_in_production(self) -> Settings:
        if self.environment == "production" and self.email_backend == "logging":
            raise ValueError(
                "EMAIL_BACKEND=logging is not permitted when ENVIRONMENT=production "
                "— a real user must actually receive verification/reset emails, not "
                "have them written to the server log. Configure a real backend."
            )
        return self

    @model_validator(mode="after")
    def _forbid_conflicting_smtp_tls_modes(self) -> Settings:
        if self.smtp_starttls and self.smtp_use_tls:
            raise ValueError(
                "SMTP_STARTTLS and SMTP_USE_TLS cannot both be true — STARTTLS upgrades "
                "a plaintext connection, SMTP_USE_TLS connects with TLS from the first "
                "byte; they are two different, mutually exclusive transport modes. Set "
                "exactly one of them true."
            )
        return self

    @model_validator(mode="after")
    def _require_smtp_config_in_production(self) -> Settings:
        if self.environment == "production" and self.email_backend == "smtp":
            missing = [
                name
                for name, value in (
                    ("SMTP_HOST", self.smtp_host),
                    ("SMTP_PORT", self.smtp_port),
                    ("SMTP_FROM_EMAIL", self.smtp_from_email),
                )
                if not value
            ]
            if missing:
                raise ValueError(
                    "EMAIL_BACKEND=smtp requires "
                    f"{', '.join(missing)} to be set when ENVIRONMENT=production — a real "
                    "user must actually receive verification/reset emails, not have the "
                    "SMTP backend fail to connect for a missing setting."
                )
            if bool(self.smtp_username) != bool(self.smtp_password):
                raise ValueError(
                    "SMTP_USERNAME and SMTP_PASSWORD must both be set or both be unset "
                    "when ENVIRONMENT=production and EMAIL_BACKEND=smtp — a lone username "
                    "or password is always a misconfiguration, never a valid credential."
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
