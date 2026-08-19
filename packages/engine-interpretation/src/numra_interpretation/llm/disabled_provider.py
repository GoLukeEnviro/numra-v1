"""An explicit "no LLM configured" `LLMProvider`.

Distinct from `MockLLMProvider`: the mock produces deterministic *content* (useful for
tests/CI), whereas `DisabledLLMProvider` produces none at all — every generation call
raises immediately. It exists so `NUMRA_LLM_PROVIDER=disabled` (the default) makes
report generation fail fast and legibly (`LLM_UNAVAILABLE`) instead of a call site
having to special-case "no provider configured" as `None`.
"""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel

from numra_interpretation.llm.errors import LLMProviderUnavailable
from numra_interpretation.llm.types import (
    GenerationRequest,
    GenerationResult,
    ProviderHealth,
    StructuredGenerationRequest,
)

__all__ = ["DisabledLLMProvider"]

_PROVIDER_NAME = "disabled"


class DisabledLLMProvider:
    """Conforms to the `LLMProvider` protocol. Always reports itself unavailable and
    never performs a network call; every generation method raises
    `LLMProviderUnavailable` immediately."""

    async def health(self) -> ProviderHealth:
        return ProviderHealth(
            status="disabled",
            provider=_PROVIDER_NAME,
            checked_at=datetime.now(UTC),
            detail="NUMRA_LLM_PROVIDER=disabled — no LLM provider is configured",
        )

    async def generate(self, request: GenerationRequest) -> GenerationResult:
        raise LLMProviderUnavailable(
            "LLM generation was requested but NUMRA_LLM_PROVIDER=disabled", retryable=False
        )

    async def generate_structured(
        self, request: StructuredGenerationRequest, schema: type[BaseModel]
    ) -> BaseModel:
        raise LLMProviderUnavailable(
            "LLM generation was requested but NUMRA_LLM_PROVIDER=disabled", retryable=False
        )
