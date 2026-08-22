from __future__ import annotations

import asyncio
import json

import httpx
import pytest
from pydantic import BaseModel

from numra_interpretation.llm.ollama_provider import OllamaCloudProvider, OllamaProviderError
from numra_interpretation.llm.types import GenerationRequest, StructuredGenerationRequest

pytestmark = pytest.mark.unit


class _StructuredSection(BaseModel):
    text: str
    metric_id: str


def test_health_is_unavailable_without_making_any_request_when_unconfigured(monkeypatch) -> None:
    monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)
    monkeypatch.delenv("OLLAMA_API_KEY", raising=False)

    def _fail_transport(request: httpx.Request) -> httpx.Response:  # pragma: no cover
        raise AssertionError("must not make a network call when unconfigured")

    provider = OllamaCloudProvider()
    health = asyncio.run(provider.health())
    assert health.status == "unavailable"
    assert "OLLAMA_BASE_URL" in (health.detail or "")


def test_health_is_unavailable_when_only_api_key_missing(monkeypatch) -> None:
    monkeypatch.setenv("OLLAMA_BASE_URL", "https://ollama.example.invalid")
    monkeypatch.delenv("OLLAMA_API_KEY", raising=False)
    provider = OllamaCloudProvider()
    health = asyncio.run(provider.health())
    assert health.status == "unavailable"


def _client_with_transport(handler) -> httpx.AsyncClient:
    transport = httpx.MockTransport(handler)
    return httpx.AsyncClient(
        base_url="https://ollama.example.invalid",
        transport=transport,
        headers={"Authorization": "Bearer test-key"},
    )


def test_health_is_healthy_when_configured_and_endpoint_responds_ok(monkeypatch) -> None:
    monkeypatch.setenv("OLLAMA_BASE_URL", "https://ollama.example.invalid")
    monkeypatch.setenv("OLLAMA_API_KEY", "test-key")

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/tags"
        return httpx.Response(200, json={"models": []})

    client = _client_with_transport(handler)
    provider = OllamaCloudProvider(client=client)
    health = asyncio.run(provider.health())
    assert health.status == "healthy"


def test_health_is_degraded_on_non_200(monkeypatch) -> None:
    monkeypatch.setenv("OLLAMA_BASE_URL", "https://ollama.example.invalid")
    monkeypatch.setenv("OLLAMA_API_KEY", "test-key")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500)

    client = _client_with_transport(handler)
    provider = OllamaCloudProvider(client=client)
    health = asyncio.run(provider.health())
    assert health.status == "degraded"


def test_generate_appends_trigger_user_message_when_no_user_instructions(monkeypatch) -> None:
    """Regression test: live against Ollama Cloud's deepseek-v4-pro/-flash models, a
    message list containing only system-role entries (no trailing user turn) returned
    an immediate empty response with done_reason="load" — no generation attempted at
    all. Every request must end with a real user-role message."""
    monkeypatch.setenv("OLLAMA_BASE_URL", "https://ollama.example.invalid")
    monkeypatch.setenv("OLLAMA_API_KEY", "test-key")

    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["payload"] = json.loads(request.content)
        return httpx.Response(
            200, json={"message": {"content": "Antworttext"}, "done_reason": "stop"}
        )

    client = _client_with_transport(handler)
    provider = OllamaCloudProvider(client=client)
    request = GenerationRequest(system_instructions="x")
    asyncio.run(provider.generate(request))

    messages = captured["payload"]["messages"]
    assert messages[-1]["role"] == "user"
    assert messages[-1]["content"]


def test_generate_sends_user_instructions_as_separate_message(monkeypatch) -> None:
    monkeypatch.setenv("OLLAMA_BASE_URL", "https://ollama.example.invalid")
    monkeypatch.setenv("OLLAMA_API_KEY", "test-key")

    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["payload"] = json.loads(request.content)
        return httpx.Response(
            200, json={"message": {"content": "Antworttext"}, "done_reason": "stop"}
        )

    client = _client_with_transport(handler)
    provider = OllamaCloudProvider(client=client)
    request = GenerationRequest(
        system_instructions="SYSTEM_MARKER",
        user_instructions="USER_MARKER_INJECTION_ATTEMPT",
    )
    result = asyncio.run(provider.generate(request))

    messages = captured["payload"]["messages"]
    assert messages[0] == {"role": "system", "content": "SYSTEM_MARKER"}
    user_messages = [m for m in messages if m["role"] == "user"]
    assert user_messages == [{"role": "user", "content": "USER_MARKER_INJECTION_ATTEMPT"}]
    # containment: user content must never appear inside the system message
    assert "USER_MARKER_INJECTION_ATTEMPT" not in messages[0]["content"]
    assert result.text == "Antworttext"
    assert result.provider == "ollama_cloud"


def test_generate_retries_then_raises_after_max_attempts(monkeypatch) -> None:
    monkeypatch.setenv("OLLAMA_BASE_URL", "https://ollama.example.invalid")
    monkeypatch.setenv("OLLAMA_API_KEY", "test-key")

    attempts = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["count"] += 1
        return httpx.Response(503)

    async def _no_sleep(_seconds: float) -> None:
        return None

    monkeypatch.setattr("numra_interpretation.llm.ollama_provider.asyncio.sleep", _no_sleep)

    client = _client_with_transport(handler)
    provider = OllamaCloudProvider(client=client)
    request = GenerationRequest(system_instructions="x")

    with pytest.raises(OllamaProviderError, match="failed after 3 attempts"):
        asyncio.run(provider.generate(request))
    assert attempts["count"] == 3


def test_generate_structured_parses_json_content_into_schema(monkeypatch) -> None:
    monkeypatch.setenv("OLLAMA_BASE_URL", "https://ollama.example.invalid")
    monkeypatch.setenv("OLLAMA_API_KEY", "test-key")

    def handler(request: httpx.Request) -> httpx.Response:
        body = {"text": "hallo", "metric_id": "life_path"}
        return httpx.Response(200, json={"message": {"content": json.dumps(body)}})

    client = _client_with_transport(handler)
    provider = OllamaCloudProvider(client=client)
    request = StructuredGenerationRequest(
        system_instructions="x", target_schema_name="_StructuredSection"
    )
    result = asyncio.run(provider.generate_structured(request, _StructuredSection))
    assert isinstance(result, _StructuredSection)
    assert result.text == "hallo"
    assert result.metric_id == "life_path"


def test_generate_structured_sends_target_json_schema_to_model(monkeypatch) -> None:
    """Regression test: `format: "json"` alone never told the model which fields to
    return, so a real reasoning model could spend its whole output budget on hidden
    thinking and return empty content (see `_build_structured_messages`). Assert the
    outgoing prompt actually carries the schema's field names."""
    monkeypatch.setenv("OLLAMA_BASE_URL", "https://ollama.example.invalid")
    monkeypatch.setenv("OLLAMA_API_KEY", "test-key")

    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["payload"] = json.loads(request.content)
        body = {"text": "hallo", "metric_id": "life_path"}
        return httpx.Response(200, json={"message": {"content": json.dumps(body)}})

    client = _client_with_transport(handler)
    provider = OllamaCloudProvider(client=client)
    request = StructuredGenerationRequest(
        system_instructions="x", target_schema_name="_StructuredSection"
    )
    asyncio.run(provider.generate_structured(request, _StructuredSection))

    messages = captured["payload"]["messages"]
    schema_messages = [m for m in messages if m["role"] == "system" and "metric_id" in m["content"]]
    assert schema_messages, f"expected the target JSON Schema in the prompt, got: {messages}"


def test_generate_structured_raises_clear_error_on_empty_content(monkeypatch) -> None:
    monkeypatch.setenv("OLLAMA_BASE_URL", "https://ollama.example.invalid")
    monkeypatch.setenv("OLLAMA_API_KEY", "test-key")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"message": {"content": ""}, "done_reason": "length"})

    client = _client_with_transport(handler)
    provider = OllamaCloudProvider(client=client)
    request = StructuredGenerationRequest(
        system_instructions="x", target_schema_name="_StructuredSection"
    )
    with pytest.raises(OllamaProviderError, match="empty content"):
        asyncio.run(provider.generate_structured(request, _StructuredSection))


def test_generate_structured_raises_on_schema_mismatch(monkeypatch) -> None:
    monkeypatch.setenv("OLLAMA_BASE_URL", "https://ollama.example.invalid")
    monkeypatch.setenv("OLLAMA_API_KEY", "test-key")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"message": {"content": json.dumps({"unexpected": 1})}})

    client = _client_with_transport(handler)
    provider = OllamaCloudProvider(client=client)
    request = StructuredGenerationRequest(
        system_instructions="x", target_schema_name="_StructuredSection"
    )
    with pytest.raises(OllamaProviderError, match="did not match"):
        asyncio.run(provider.generate_structured(request, _StructuredSection))


def test_reads_model_env_vars(monkeypatch) -> None:
    monkeypatch.setenv("OLLAMA_BASE_URL", "https://ollama.example.invalid")
    monkeypatch.setenv("OLLAMA_API_KEY", "test-key")
    monkeypatch.setenv("NUMRA_LLM_MODEL_FAST", "custom-fast-model")
    monkeypatch.setenv("NUMRA_LLM_MODEL_PREMIUM", "custom-premium-model")

    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["payload"] = json.loads(request.content)
        return httpx.Response(200, json={"message": {"content": "ok"}})

    client = _client_with_transport(handler)
    provider = OllamaCloudProvider(client=client)
    asyncio.run(provider.generate(GenerationRequest(system_instructions="x")))
    assert captured["payload"]["model"] == "custom-fast-model"
