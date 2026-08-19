from __future__ import annotations

import asyncio

import pytest

from numra_interpretation.llm.mock_provider import MockLLMProvider
from numra_interpretation.llm.ollama_provider import OllamaCloudProvider
from numra_interpretation.llm.types import GenerationRequest, LLMProvider

pytestmark = pytest.mark.unit


async def _run_health_check(provider: LLMProvider) -> str:
    """Written against the `LLMProvider` Protocol only — proves callers can depend on
    the interface without knowing the concrete provider."""
    health = await provider.health()
    return health.status


def test_mock_provider_satisfies_llm_provider_protocol() -> None:
    provider: LLMProvider = MockLLMProvider()
    assert asyncio.run(_run_health_check(provider)) == "healthy"


def test_ollama_provider_satisfies_llm_provider_protocol_when_unconfigured(monkeypatch) -> None:
    monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)
    monkeypatch.delenv("OLLAMA_API_KEY", raising=False)
    provider: LLMProvider = OllamaCloudProvider()
    assert asyncio.run(_run_health_check(provider)) == "unavailable"


def test_swapping_providers_behind_the_same_call_site(monkeypatch) -> None:
    monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)
    monkeypatch.delenv("OLLAMA_API_KEY", raising=False)

    providers: list[LLMProvider] = [MockLLMProvider(), OllamaCloudProvider()]
    statuses = [asyncio.run(_run_health_check(p)) for p in providers]
    assert statuses == ["healthy", "unavailable"]


def test_generate_call_site_is_provider_agnostic() -> None:
    """A caller written against `generate()` alone must work for the mock without any
    provider-specific branching."""
    provider: LLMProvider = MockLLMProvider()
    request = GenerationRequest(system_instructions="Erkläre kurz und sachlich.")
    result = asyncio.run(provider.generate(request))
    assert result.text
    assert result.provider == "mock"
