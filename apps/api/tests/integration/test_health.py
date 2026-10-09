from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from numra_api.app import create_app
from numra_api.config import Settings
from numra_api.db import build_sessionmaker
from numra_api.routes import health as health_routes

pytestmark = pytest.mark.integration


async def test_live(client) -> None:
    response = await client.get("/v1/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "live"}


async def test_ready_with_mock_llm_and_real_pdf_service(client) -> None:
    """The `client`/`settings` fixtures use numra_llm_provider="mock" and point
    pdf_internal_url at a real apps/pdf instance (TEST_PDF_URL) — a genuine, not
    config-only, check of each dependency, run against the actual test database and a
    real PDF service render/health call."""
    response = await client.get("/v1/health/ready")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "healthy"
    assert body["database"] == "healthy"
    assert body["numerology_engine"] == "healthy"
    assert body["llm"] == "healthy"
    assert body["pdf"] == "healthy"


async def test_ready_reports_pdf_disabled_when_url_unset(settings, db_engine) -> None:
    no_pdf_settings = Settings(
        database_url=settings.database_url, environment="test", numra_llm_provider="mock"
    )
    app = create_app(settings=no_pdf_settings)
    app.state.engine = db_engine
    app.state.sessionmaker = build_sessionmaker(db_engine)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/v1/health/ready")
    assert response.status_code == 200
    assert response.json()["pdf"] == "disabled"


async def test_ready_reports_pdf_unhealthy_when_configured_but_unreachable(
    settings, db_engine
) -> None:
    unreachable_pdf_settings = Settings(
        database_url=settings.database_url,
        environment="test",
        numra_llm_provider="mock",
        pdf_internal_url="http://127.0.0.1:1",  # nothing listens here
        health_check_timeout_seconds=1.0,
    )
    app = create_app(settings=unreachable_pdf_settings)
    app.state.engine = db_engine
    app.state.sessionmaker = build_sessionmaker(db_engine)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/v1/health/ready")
    assert response.status_code == 200
    assert response.json()["pdf"] == "unhealthy"


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


async def test_ready_returns_503_with_full_body_when_database_unhealthy(
    settings, db_engine, monkeypatch
) -> None:
    async def _database_down(*_args: object, **_kwargs: object) -> str:
        return "unhealthy"

    monkeypatch.setattr(health_routes, "_check_database", _database_down)
    app = create_app(
        settings=Settings(
            database_url=settings.database_url, environment="test", numra_llm_provider="mock"
        )
    )
    app.state.engine = db_engine
    app.state.sessionmaker = build_sessionmaker(db_engine)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/v1/health/ready")
        cached = await client.get("/v1/health/ready")
    expected = {
        "status": "unhealthy",
        "database": "unhealthy",
        "numerology_engine": "healthy",
        "llm": "healthy",
        "pdf": "disabled",
    }
    assert response.status_code == 503
    assert response.json() == expected
    # Der TTL-Cache liefert denselben Zustand, also auch denselben Statuscode.
    assert cached.status_code == 503
    assert cached.json() == expected


async def test_ready_stays_200_when_only_optional_dependencies_are_down(
    settings, db_engine
) -> None:
    app = create_app(
        settings=Settings(
            database_url=settings.database_url,
            environment="test",
            numra_llm_provider="mock",
            pdf_internal_url="http://127.0.0.1:1",  # nothing listens here
            health_check_timeout_seconds=1.0,
        )
    )
    app.state.engine = db_engine
    app.state.sessionmaker = build_sessionmaker(db_engine)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/v1/health/ready")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"
    assert response.json()["pdf"] == "unhealthy"


@pytest.mark.parametrize(
    ("database_state", "expected_status_code"),
    [("unhealthy", 503), ("healthy", 200)],
)
async def test_ready_cache_path_keeps_status_code_without_rechecking(
    settings, db_engine, monkeypatch, database_state: str, expected_status_code: int
) -> None:
    calls = 0

    async def _database_check(*_args: object, **_kwargs: object) -> str:
        nonlocal calls
        calls += 1
        return database_state

    monkeypatch.setattr(health_routes, "_check_database", _database_check)
    app = create_app(
        settings=Settings(
            database_url=settings.database_url,
            environment="test",
            numra_llm_provider="mock",
            health_ready_cache_ttl_seconds=60.0,
        )
    )
    app.state.engine = db_engine
    app.state.sessionmaker = build_sessionmaker(db_engine)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        first = await client.get("/v1/health/ready")
        second = await client.get("/v1/health/ready")
    assert calls == 1
    assert first.status_code == expected_status_code
    assert second.status_code == expected_status_code
    assert second.json() == first.json()
