"""A real async HTTP `LLMProvider` backed by an Ollama-compatible chat/generate API.

Configuration is entirely env-var driven (never hardcoded):

- ``OLLAMA_BASE_URL`` — base URL of the Ollama-compatible endpoint.
- ``OLLAMA_API_KEY`` — bearer token.
- ``NUMRA_LLM_MODEL_PREMIUM`` / ``NUMRA_LLM_MODEL_FAST`` — model identifiers.
- ``NUMRA_LLM_TIMEOUT_SECONDS`` — per-request timeout.

NOTE ON MODEL DEFAULTS: the ``_DEFAULT_MODEL_*`` fallbacks below are placeholders used
only when the corresponding env var is unset — they are picked to look like plausible
Ollama model names, not because live availability against any real Ollama Cloud
deployment has been verified in this repo/CI. Production deployments MUST set
``NUMRA_LLM_MODEL_PREMIUM``/``NUMRA_LLM_MODEL_FAST`` explicitly.

If the base URL or API key are absent, `health()` returns ``status="unavailable"``
cleanly — it never raises, so a missing LLM configuration can never crash the
surrounding application (canon-spec.md determinism-adjacent principle: the engine/API
must degrade, not crash, when the optional LLM layer is unconfigured).

Prompt-injection containment: `request.user_instructions` is passed as its own
``role: "user"`` chat message — it is never concatenated into the ``system`` message
string alongside `request.system_instructions`.
"""

from __future__ import annotations

import asyncio
import json
import os
from datetime import UTC, datetime
from typing import Any

import httpx
from pydantic import BaseModel, ValidationError

from numra_interpretation.llm.types import (
    GenerationRequest,
    GenerationResult,
    ProviderHealth,
    StructuredGenerationRequest,
)

__all__ = ["OllamaCloudProvider", "OllamaProviderError"]

_PROVIDER_NAME = "ollama_cloud"

# See the module docstring's "NOTE ON MODEL DEFAULTS" — unverified placeholders.
_DEFAULT_MODEL_PREMIUM = "llama3.1:70b"
_DEFAULT_MODEL_FAST = "llama3.1:8b"
_DEFAULT_TIMEOUT_SECONDS = 30.0
_MAX_RETRIES = 3
_BACKOFF_BASE_SECONDS = 0.5


class OllamaProviderError(Exception):
    """Raised for a request that failed after exhausting all retries, or that returned
    a response the provider could not parse/validate. Never raised by `health()`."""


def _read_timeout_seconds() -> float:
    raw = os.environ.get("NUMRA_LLM_TIMEOUT_SECONDS")
    if raw is None:
        return _DEFAULT_TIMEOUT_SECONDS
    try:
        return float(raw)
    except ValueError:
        return _DEFAULT_TIMEOUT_SECONDS


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
    """Conforms to the `LLMProvider` protocol. Constructor accepts an optional
    pre-built `httpx.AsyncClient` for testability (tests inject a mocked transport
    instead of hitting a real network)."""

    def __init__(self, *, client: httpx.AsyncClient | None = None) -> None:
        self._base_url = os.environ.get("OLLAMA_BASE_URL")
        self._api_key = os.environ.get("OLLAMA_API_KEY")
        self._model_premium = os.environ.get("NUMRA_LLM_MODEL_PREMIUM", _DEFAULT_MODEL_PREMIUM)
        self._model_fast = os.environ.get("NUMRA_LLM_MODEL_FAST", _DEFAULT_MODEL_FAST)
        self._timeout_seconds = _read_timeout_seconds()
        self._client = client

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

    async def _post_chat_with_retry(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not self._is_configured():
            raise OllamaProviderError(
                "OllamaCloudProvider is not configured (OLLAMA_BASE_URL/OLLAMA_API_KEY "
                "missing); call health() first to check availability without raising."
            )

        client = self._get_client()
        last_error: Exception | None = None
        for attempt in range(_MAX_RETRIES):
            try:
                response = await client.post("/api/chat", json=payload)
                response.raise_for_status()
                data: dict[str, Any] = response.json()
                return data
            except (httpx.HTTPError, json.JSONDecodeError) as exc:
                last_error = exc
                if attempt < _MAX_RETRIES - 1:
                    await asyncio.sleep(_BACKOFF_BASE_SECONDS * (2**attempt))
        raise OllamaProviderError(
            f"Ollama chat request failed after {_MAX_RETRIES} attempts: {last_error}"
        ) from last_error

    async def generate(self, request: GenerationRequest) -> GenerationResult:
        model = self._model_fast
        payload = {"model": model, "messages": _build_messages(request), "stream": False}
        data = await self._post_chat_with_retry(payload)
        try:
            text = data["message"]["content"]
        except (KeyError, TypeError) as exc:
            raise OllamaProviderError(f"Unexpected Ollama chat response shape: {data}") from exc

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
        }
        data = await self._post_chat_with_retry(payload)
        try:
            raw_content = data["message"]["content"]
        except (KeyError, TypeError) as exc:
            raise OllamaProviderError(f"Unexpected Ollama chat response shape: {data}") from exc

        try:
            parsed = json.loads(raw_content)
        except json.JSONDecodeError as exc:
            raise OllamaProviderError(
                f"Ollama structured response was not valid JSON: {raw_content!r}"
            ) from exc

        try:
            return schema.model_validate(parsed)
        except ValidationError as exc:
            raise OllamaProviderError(
                f"Ollama structured response did not match {schema.__name__}: {exc}"
            ) from exc
