"""Builds the single `LLMProvider` the worker/report pipeline uses, from `Settings`.

This is the *only* place a concrete provider class is chosen. `NUMRA_LLM_PROVIDER` is
the sole source of truth for provider selection — nothing here falls back silently from
one provider to another. In particular, an "ollama" selection with missing
`OLLAMA_BASE_URL`/`OLLAMA_API_KEY` still returns a real `OllamaCloudProvider`: its
`health()` will legitimately report "unavailable" and report generation will fail with
a clear `LLM_UNAVAILABLE` error, rather than this factory quietly substituting the mock.
"""

from __future__ import annotations

from numra_api.config import Settings
from numra_interpretation.llm.disabled_provider import DisabledLLMProvider
from numra_interpretation.llm.mock_provider import MockLLMProvider
from numra_interpretation.llm.ollama_provider import OllamaCloudProvider
from numra_interpretation.llm.types import LLMProvider

__all__ = ["build_llm_provider"]


def build_llm_provider(settings: Settings) -> LLMProvider:
    """Construct the `LLMProvider` selected by ``settings.numra_llm_provider``.

    ``Settings`` already forbids ``numra_llm_provider="mock"`` when
    ``environment="production"`` (see `Settings._forbid_mock_llm_provider_in_production`)
    — that check runs at settings-construction time, so by the time this factory runs
    the combination is already known to be safe. This function does not re-validate it;
    it trusts the `Settings` instance it is given.
    """
    if settings.numra_llm_provider == "ollama":
        return OllamaCloudProvider(
            base_url=settings.ollama_base_url,
            api_key=settings.ollama_api_key,
            model_premium=settings.numra_llm_model_premium,
            model_fast=settings.numra_llm_model_fast,
            timeout_seconds=float(settings.numra_llm_timeout_seconds),
            temperature=settings.numra_llm_temperature,
            max_retries=settings.numra_llm_max_retries,
        )
    if settings.numra_llm_provider == "mock":
        return MockLLMProvider()
    return DisabledLLMProvider()
