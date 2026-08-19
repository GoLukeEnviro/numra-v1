"""A real async HTTP `LLMProvider` backed by an Ollama-compatible chat/generate API.

Configuration is passed explicitly by the caller (clean dependency injection — see
``apps/api/src/numra_api/services/llm_factory.py``, which reads the application's
``Settings`` model and passes every value in here as a constructor argument). Every
constructor parameter falls back to reading the matching environment variable only
when the caller omits it, so this class still works standalone (e.g. in a script or a
test) without needing a Settings object.

NOTE ON MODEL DEFAULTS: the ``_DEFAULT_MODEL_*`` fallbacks below are placeholders used
only when neither an explicit argument nor the corresponding env var is set — they are
picked to look like plausible Ollama model names, not because live availability
against any real Ollama Cloud deployment has been verified in this repo/CI. Production
deployments MUST set ``NUMRA_LLM_MODEL_PREMIUM``/``NUMRA_LLM_MODEL_FAST`` explicitly.

If the base URL or API key are absent, `health()` returns ``status="unavailable"``
cleanly — it never raises, so a missing LLM configuration can never crash the
surrounding application (canon-spec.md determinism-adjacent principle: the engine/API
must degrade, not crash, when the optional LLM layer is unconfigured).

Prompt-injection containment: `request.user_instructions` is passed as its own
``role: "user"`` chat message — it is never concatenated into the ``system`` message
string alongside `request.system_instructions`.

Failures are normalized onto the `numra_interpretation.llm.errors` taxonomy
(`LLMProviderTimeout`, `LLMProviderRateLimited`, `LLMProviderInternalError`,
`LLMProviderUnavailable`, `LLMInvalidStructuredResponse`) so callers (the report job
queue) can decide retryability without knowing this is specifically Ollama.
`OllamaProviderError` is kept as the common base of all of them, for backward
compatibility with call sites/tests that only care "was it an Ollama failure".
"""

from __future__ import annotations

import asyncio
import json
import os
from datetime import UTC, datetime
from typing import Any

import httpx
from pydantic import BaseModel, ValidationError

from numra_interpretation.llm.errors import (
    LLMInvalidStructuredResponse,
    LLMProviderError,
    LLMProviderInternalError,
    LLMProviderRateLimited,
    LLMProviderTimeout,
    LLMProviderUnavailable,
)
from numra_interpretation.llm.types import (
    GenerationRequest,
    GenerationResult,
    ProviderHealth,
    StructuredGenerationRequest,
)

__all__ = [
    "OllamaCloudProvider",
    "OllamaInternalError",
    "OllamaInvalidStructuredResponseError",
    "OllamaProviderError",
    "OllamaRateLimitedError",
    "OllamaTimeoutError",
    "OllamaUnavailableError",
]

_PROVIDER_NAME = "ollama_cloud"

# See the module docstring's "NOTE ON MODEL DEFAULTS" — unverified placeholders.
_DEFAULT_MODEL_PREMIUM = "llama3.1:70b"
_DEFAULT_MODEL_FAST = "llama3.1:8b"
_DEFAULT_TIMEOUT_SECONDS = 30.0
_DEFAULT_MAX_RETRIES = 3
_DEFAULT_TEMPERATURE = 0.2
_BACKOFF_BASE_SECONDS = 0.5


class OllamaProviderError(LLMProviderError):
    """Base for all Ollama-specific failures. Kept as the common ancestor of the more
    specific classes below so existing ``except OllamaProviderError`` / ``pytest.raises
    (OllamaProviderError)`` call sites keep working regardless of which specific
    failure occurred."""


class OllamaUnavailableError(OllamaProviderError, LLMProviderUnavailable):
    pass


class OllamaTimeoutError(OllamaProviderError, LLMProviderTimeout):
    pass


class OllamaRateLimitedError(OllamaProviderError, LLMProviderRateLimited):
    pass


class OllamaInternalError(OllamaProviderError, LLMProviderInternalError):
    pass


class OllamaInvalidStructuredResponseError(OllamaProviderError, LLMInvalidStructuredResponse):
    pass


def _read_env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _read_env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _build_messages(request: GenerationRequest) -> list[dict[str, str]]:
    """Role-tagged chat messages. Each context block becomes its own message so
    nothing is string-concatenated together, and `user_instructions` — the one field
    that may carry end-user-supplied content — is always its own trailing ``user``
    message, never folded into the ``system`` message."""
    messages: list[dict[str, str]] = [{"role": "system", "content": request.system_instructions}]
    for block in request.context_blocks:
        messages.append(
            {"role": "system", "content": f"[{block.role}:{block.label}] {block.content}"}
        )
    if request.user_instructions is not None:
        messages.append({"role": "user", "content": request.user_instructions})
    return messages


class OllamaCloudProvider:
    """Conforms to the `LLMProvider` protocol. Every configuration value is an
    explicit constructor argument (dependency injection) with an environment-variable
    fallback for standalone use; ``client`` accepts a pre-built `httpx.AsyncClient` for
    testability (tests inject a mocked transport instead of hitting a real network)."""

    def __init__(
        self,
        *,
        base_url: str | None = None,
        api_key: str | None = None,
        model_premium: str | None = None,
        model_fast: str | None = None,
        timeout_seconds: float | None = None,
        temperature: float | None = None,
        max_retries: int | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._base_url = base_url if base_url is not None else os.environ.get("OLLAMA_BASE_URL")
        self._api_key = api_key if api_key is not None else os.environ.get("OLLAMA_API_KEY")
        self._model_premium = model_premium or os.environ.get(
            "NUMRA_LLM_MODEL_PREMIUM", _DEFAULT_MODEL_PREMIUM
        )
        self._model_fast = model_fast or os.environ.get(
            "NUMRA_LLM_MODEL_FAST", _DEFAULT_MODEL_FAST
        )
        self._timeout_seconds = (
            timeout_seconds
            if timeout_seconds is not None
            else _read_env_float("NUMRA_LLM_TIMEOUT_SECONDS", _DEFAULT_TIMEOUT_SECONDS)
        )
        self._temperature = (
            temperature
            if temperature is not None
            else _read_env_float("NUMRA_LLM_TEMPERATURE", _DEFAULT_TEMPERATURE)
        )
        self._max_retries = (
            max_retries
            if max_retries is not None
            else _read_env_int("NUMRA_LLM_MAX_RETRIES", _DEFAULT_MAX_RETRIES)
        )
        self._client = client

    @property
    def provider_name(self) -> str:
        return _PROVIDER_NAME

    @property
    def premium_model(self) -> str:
        return self._model_premium

    @property
    def fast_model(self) -> str:
        return self._model_fast

    def _is_configured(self) -> bool:
        return bool(self._base_url) and bool(self._api_key)

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is not None:
            return self._client
        assert self._base_url is not None  # only called when _is_configured() is True
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            headers={"Authorization": f"Bearer {self._api_key}"},
            timeout=self._timeout_seconds,
        )
        return self._client

    async def health(self) -> ProviderHealth:
        if not self._is_configured():
            return ProviderHealth(
                status="unavailable",
                provider=_PROVIDER_NAME,
                checked_at=datetime.now(UTC),
                detail="OLLAMA_BASE_URL and/or OLLAMA_API_KEY not set",
            )

        client = self._get_client()
        try:
            response = await client.get("/api/tags")
        except httpx.HTTPError as exc:
            return ProviderHealth(
                status="unavailable",
                provider=_PROVIDER_NAME,
                checked_at=datetime.now(UTC),
                detail=f"health check request failed: {exc}",
            )

        if response.status_code == httpx.codes.OK:
            return ProviderHealth(
                status="healthy", provider=_PROVIDER_NAME, checked_at=datetime.now(UTC)
            )
        return ProviderHealth(
            status="degraded",
            provider=_PROVIDER_NAME,
            checked_at=datetime.now(UTC),
            detail=f"health check returned HTTP {response.status_code}",
        )

    def _classify_http_error(self, exc: Exception, attempts: int) -> OllamaProviderError:
        if isinstance(exc, httpx.TimeoutException):
            return OllamaTimeoutError(f"Ollama request timed out after {attempts} attempts: {exc}")
        if isinstance(exc, httpx.HTTPStatusError):
            status = exc.response.status_code
            if status == httpx.codes.TOO_MANY_REQUESTS:
                return OllamaRateLimitedError(
                    f"Ollama rate-limited the request after {attempts} attempts: {exc}"
                )
            if status >= 500:
                return OllamaInternalError(
                    f"Ollama request failed after {attempts} attempts (server error): {exc}"
                )
            # A non-retryable 4xx (bad request, auth, etc.) — still surfaced as a
            # provider error, but callers should not expect a retry to help.
            return OllamaInternalError(
                f"Ollama request failed after {attempts} attempts (HTTP {status}): {exc}",
                retryable=False,
            )
        if isinstance(exc, httpx.HTTPError):
            return OllamaUnavailableError(
                f"Ollama request failed after {attempts} attempts (unreachable): {exc}"
            )
        if isinstance(exc, json.JSONDecodeError):
            return OllamaInvalidStructuredResponseError(
                f"Ollama request failed after {attempts} attempts (invalid JSON): {exc}"
            )
        return OllamaInternalError(f"Ollama request failed after {attempts} attempts: {exc}")

    async def _post_chat_with_retry(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not self._is_configured():
            raise OllamaUnavailableError(
                "OllamaCloudProvider is not configured (OLLAMA_BASE_URL/OLLAMA_API_KEY "
                "missing); call health() first to check availability without raising."
            )

        client = self._get_client()
        last_error: Exception | None = None
        for attempt in range(self._max_retries):
            try:
                response = await client.post("/api/chat", json=payload)
                response.raise_for_status()
                data: dict[str, Any] = response.json()
                return data
            except (httpx.HTTPError, json.JSONDecodeError) as exc:
                last_error = exc
                if attempt < self._max_retries - 1:
                    await asyncio.sleep(_BACKOFF_BASE_SECONDS * (2**attempt))
        assert last_error is not None
        raise self._classify_http_error(last_error, self._max_retries)

    async def generate(self, request: GenerationRequest) -> GenerationResult:
        model = self._model_fast
        payload = {
            "model": model,
            "messages": _build_messages(request),
            "stream": False,
            "options": {"temperature": self._temperature},
        }
        data = await self._post_chat_with_retry(payload)
        try:
            text = data["message"]["content"]
        except (KeyError, TypeError) as exc:
            raise OllamaInvalidStructuredResponseError(
                f"Unexpected Ollama chat response shape: {data}"
            ) from exc

        return GenerationResult(
            text=text,
            numeric_claims=request.numeric_claims,
            provider=_PROVIDER_NAME,
            model=model,
            finish_reason=data.get("done_reason"),
        )

    async def generate_structured(
        self, request: StructuredGenerationRequest, schema: type[BaseModel]
    ) -> BaseModel:
        model = self._model_premium
        payload = {
            "model": model,
            "messages": _build_messages(request),
            "format": "json",
            "stream": False,
            "options": {"temperature": self._temperature},
        }
        data = await self._post_chat_with_retry(payload)
        try:
            raw_content = data["message"]["content"]
        except (KeyError, TypeError) as exc:
            raise OllamaInvalidStructuredResponseError(
                f"Unexpected Ollama chat response shape: {data}"
            ) from exc

        try:
            parsed = json.loads(raw_content)
        except json.JSONDecodeError as exc:
            raise OllamaInvalidStructuredResponseError(
                f"Ollama structured response was not valid JSON: {raw_content!r}"
            ) from exc

        try:
            return schema.model_validate(parsed)
        except ValidationError as exc:
            raise OllamaInvalidStructuredResponseError(
                f"Ollama structured response did not match {schema.__name__}: {exc}"
            ) from exc
