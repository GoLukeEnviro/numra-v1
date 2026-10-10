from __future__ import annotations

import ipaddress
from functools import lru_cache
from typing import Annotated, Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

from numra_api.rate_limit.policies import DEFAULT_POLICIES, parse_policy_spec

_MIN_PROXY_SECRET_LENGTH = 32

LLMProviderName = Literal["ollama", "mock", "disabled"]
RateLimitBackend = Literal["memory", "redis"]
EmailBackend = Literal["logging", "disabled", "smtp"]


class Settings(BaseSettings):
    #: `env_ignore_empty` is what makes the compose passthrough pattern safe: the
    #: stack forwards optional transport settings with empty defaults
    #: (`SMTP_PORT: ${SMTP_PORT:-}`), and an empty env value must mean "unset"
    #: (fall back to the field default) instead of failing int/bool parsing for
    #: deployments that do not configure SMTP at all.
    #: `hide_input_in_errors`: ein Validierungsfehler darf den Roh-Eingabewert (z. B. ein
    #: zu kurzes Secret oder das SMTP-Passwort) nie in Logs/Tracebacks spiegeln.
    model_config = SettingsConfigDict(
        env_file=".env", extra="ignore", env_ignore_empty=True, hide_input_in_errors=True
    )

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
    numra_llm_model_premium: str = "deepseek-v4-pro:0813"
    numra_llm_model_fast: str = "deepseek-v4.1-flash"
    numra_llm_temperature: float = 1.0
    numra_llm_top_p: float = 1.0
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
    #: Überschreibt Auth-Rate-Limit-Policies (siehe rate_limit/policies.py), z. B.
    #: RATE_LIMIT_OVERRIDES='{"auth:login:target": "30/900"}'.
    rate_limit_overrides: dict[str, str] = {}

    log_level: str = "INFO"
    report_max_words: int = 30_000

    cors_allowed_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    #: D4 closed beta: when true, the cost-intensive features (report generation,
    #: relationship/shadow/pattern analyses, Copilot messages) additionally require an
    #: individual beta grant (an `EntitlementAssignment`, see
    #: services/beta_gate.py) on top of the global feature flag. Default false = no
    #: behavior change on deploy; docs/ops/2026-10-09-d4-beta-transition.md fixes the
    #: order (deploy gate off -> inventory -> backfill -> enforce).
    beta_gate_enforced: bool = False

    #: D4 quotas per user and feature group. Every limit defaults to None = unlimited, so
    #: without configuration nothing is counted or written. ``*_max``: units per sliding
    #: ``*_window_seconds``; ``*_max_concurrent``: units in flight (queued/running job or
    #: Copilot message being answered). Recommendations: docs/ops/2026-10-10-d4-limits-and-budget.md
    quota_report_max: int | None = Field(default=None, ge=1)
    quota_report_window_seconds: int = Field(default=86_400, ge=1)
    quota_report_max_concurrent: int | None = Field(default=None, ge=1)
    quota_analysis_max: int | None = Field(default=None, ge=1)
    quota_analysis_window_seconds: int = Field(default=86_400, ge=1)
    quota_analysis_max_concurrent: int | None = Field(default=None, ge=1)
    quota_copilot_max: int | None = Field(default=None, ge=1)
    quota_copilot_window_seconds: int = Field(default=86_400, ge=1)
    quota_copilot_max_concurrent: int | None = Field(default=None, ge=1)
    #: A unit still "active" after this long is treated as abandoned (crashed process)
    #: and stops blocking the concurrency limit. Must exceed the longest job lifetime.
    quota_active_stale_seconds: int = Field(default=3_600, ge=60)

    request_body_max_bytes: int = 2 * 1024 * 1024

    #: Gemeinsames Secret zwischen Web-BFF und API (Header `X-Numra-Proxy-Auth`). Nur
    #: serverseitig; `SecretStr`, damit es nie in repr()/Logs erscheint. `_previous` ist
    #: der Rotations-/Rückrollpfad: beide Werte sind gleichzeitig gültig.
    internal_proxy_shared_secret: SecretStr | None = None
    internal_proxy_shared_secret_previous: SecretStr | None = None
    #: false = Übergangsmodus (Header optional, ungültiger Header wird ignoriert);
    #: true = Behauptete Proxy-Identität und Cookie-Sessions brauchen ein gültiges Secret.
    proxy_secret_enforced: bool = False
    #: Peer-Adressen (CIDR, kommagetrennt), von denen eine weitergeleitete Client-IP
    #: akzeptiert wird -- zusätzlich zum gültigen Secret. Leer = nie.
    trusted_proxy_cidrs: Annotated[list[str], NoDecode] = []

    #: Deliberately a Settings field (unlike routes/public.py's former APP_NAME
    #: constant) -- branding is not a security-relevant value like
    #: `allow_self_signup`, so letting a deployment configure it carries none of the
    #: risk that letting one configure e.g. session/CSRF behavior would.
    app_brand_name: str = "AVENYTH"

    #: "logging" only logs the email instead of sending it -- fine when local dev/CI/E2E
    #: selects it explicitly, never for real users; not permitted when
    #: ENVIRONMENT=production (see the validator below). "disabled" is the safe default
    #: and the `numra_llm_provider="disabled"` analogue:
    #: no real send mechanism exists in V1 (see email/sender.py), so it is what a
    #: production deployment configures today -- request-email-verification/
    #: forgot-password fail fast and legibly rather than one of them being silently
    #: mislabeled "sent". Same three-way shape as `numra_llm_provider`.
    email_backend: EmailBackend = "disabled"
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

    @field_validator("trusted_proxy_cidrs", mode="before")
    @classmethod
    def _split_trusted_proxy_cidrs(cls, value: object) -> object:
        if isinstance(value, str):
            return [part.strip() for part in value.split(",") if part.strip()]
        return value

    @field_validator("trusted_proxy_cidrs")
    @classmethod
    def _validate_trusted_proxy_cidrs(cls, value: list[str]) -> list[str]:
        for cidr in value:
            try:
                ipaddress.ip_network(cidr, strict=False)
            except ValueError:
                raise ValueError(
                    f"TRUSTED_PROXY_CIDRS enthält keine gültige CIDR: {cidr!r}"
                ) from None
        return value

    @model_validator(mode="after")
    def _validate_proxy_secrets(self) -> Settings:
        current = self.internal_proxy_shared_secret
        previous = self.internal_proxy_shared_secret_previous
        for name, secret in (
            ("INTERNAL_PROXY_SHARED_SECRET", current),
            ("INTERNAL_PROXY_SHARED_SECRET_PREVIOUS", previous),
        ):
            if secret is not None and len(secret.get_secret_value()) < _MIN_PROXY_SECRET_LENGTH:
                raise ValueError(
                    f"{name} muss mindestens {_MIN_PROXY_SECRET_LENGTH} Zeichen haben."
                )
        if previous is not None and current is None:
            raise ValueError(
                "INTERNAL_PROXY_SHARED_SECRET_PREVIOUS erfordert INTERNAL_PROXY_SHARED_SECRET."
            )
        if (
            previous is not None
            and current is not None
            and previous.get_secret_value() == current.get_secret_value()
        ):
            raise ValueError(
                "INTERNAL_PROXY_SHARED_SECRET_PREVIOUS darf nicht dem aktuellen Secret entsprechen."
            )
        if self.proxy_secret_enforced and current is None:
            raise ValueError("PROXY_SECRET_ENFORCED=true erfordert INTERNAL_PROXY_SHARED_SECRET.")
        return self

    @field_validator("rate_limit_overrides")
    @classmethod
    def _validate_rate_limit_overrides(cls, value: dict[str, str]) -> dict[str, str]:
        for policy, spec in value.items():
            if policy not in DEFAULT_POLICIES:
                raise ValueError(f"RATE_LIMIT_OVERRIDES: unbekannte Policy {policy!r}")
            try:
                parse_policy_spec(spec)
            except ValueError as exc:
                raise ValueError(f"RATE_LIMIT_OVERRIDES[{policy!r}]: {exc}") from None
        return value

    def rate_limit_policy(self, policy: str) -> tuple[int, int]:
        """(limit, window_seconds) einer benannten Policy, Override vor Default."""
        override = self.rate_limit_overrides.get(policy)
        return parse_policy_spec(override) if override else DEFAULT_POLICIES[policy]

    @property
    def proxy_secret_values(self) -> list[str]:
        return [
            s.get_secret_value()
            for s in (self.internal_proxy_shared_secret, self.internal_proxy_shared_secret_previous)
            if s is not None
        ]

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
