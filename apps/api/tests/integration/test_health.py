from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from numra_api.app import create_app
from numra_api.config import Settings
from numra_api.db import build_sessionmaker

pytestmark = pytest.mark.integration


async def test_live(client) -> None:
    response = await client.get("/v1/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "live"}


async def test_ready_with_mock_llm_and_no_pdf_configured(client) -> None:
    """The `client`/`settings` fixtures use numra_llm_provider="mock" and leave
    pdf_internal_url unset — a real (not config-only) check of each dependency, run
    against the actual test database."""
    response = await client.get("/v1/health/ready")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "healthy"
    assert body["database"] == "healthy"
    assert body["numerology_engine"] == "healthy"
    assert body["llm"] == "healthy"
    assert body["pdf"] == "disabled"


async def test_ready_reports_llm_disabled_when_provider_is_disabled(settings, db_engine) -> None:
    disabled_settings = Settings(
        database_url=settings.database_url, environment="test", numra_llm_provider="disabled"
    )
    app = create_app(settings=disabled_settings)
    app.state.engine = db_engine
    app.state.sessionmaker = build_sessionmaker(db_engine)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/v1/health/ready")
    assert response.status_code == 200
    body = response.json()
    assert body["llm"] == "disabled"
    assert body["status"] == "healthy"  # LLM being disabled does not make the app unready


async def test_ready_reports_llm_unhealthy_when_ollama_configured_but_unreachable(
    settings, db_engine
) -> None:
    ollama_settings = Settings(
        database_url=settings.database_url,
        environment="test",
        numra_llm_provider="ollama",
        ollama_base_url="http://127.0.0.1:1",  # nothing listens here
        ollama_api_key="test-key",
        health_check_timeout_seconds=1.0,
    )
    app = create_app(settings=ollama_settings)
    app.state.engine = db_engine
    app.state.sessionmaker = build_sessionmaker(db_engine)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/v1/health/ready")
    assert response.status_code == 200
    body = response.json()
    assert body["llm"] == "unhealthy"


async def test_ready_response_is_cached_for_the_configured_ttl(settings, db_engine) -> None:
    cached_settings = Settings(
        database_url=settings.database_url,
        environment="test",
        numra_llm_provider="mock",
        health_ready_cache_ttl_seconds=60.0,
    )
    app = create_app(settings=cached_settings)
    app.state.engine = db_engine
    app.state.sessionmaker = build_sessionmaker(db_engine)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        first = await client.get("/v1/health/ready")
        assert first.status_code == 200
        cache_after_first = app.state.health_ready_cache
        assert cache_after_first is not None

        second = await client.get("/v1/health/ready")
        assert second.status_code == 200
        # The cached payload object is returned verbatim on the second call — the
        # cache entry itself must not have been rebuilt.
        assert app.state.health_ready_cache is cache_after_first
