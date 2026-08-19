from __future__ import annotations

import uuid

import pytest

from numra_api.app import create_app
from numra_api.auth.passwords import hash_password
from numra_api.config import Settings
from numra_api.db import build_sessionmaker
from numra_api.repositories.users import create_user

pytestmark = pytest.mark.integration


async def _login(client, sessionmaker, email: str = "notfound@example.com") -> dict:
    async with sessionmaker() as db:
        await create_user(db, email=email, password_hash=hash_password("password12345"))
        await db.commit()
    response = await client.post(
        "/v1/auth/login", json={"email": email, "password": "password12345"}
    )
    assert response.status_code == 200
    return {"x-csrf-token": client.cookies["numra_csrf"]}


async def test_get_missing_person_404(client, sessionmaker) -> None:
    headers = await _login(client, sessionmaker)
    response = await client.get(f"/v1/people/{uuid.uuid4()}", headers=headers)
    assert response.status_code == 404
    assert response.json()["code"] == "NOT_FOUND"


async def test_patch_missing_person_404(client, sessionmaker) -> None:
    headers = await _login(client, sessionmaker)
    response = await client.patch(
        f"/v1/people/{uuid.uuid4()}", json={"preferred_name": "X"}, headers=headers
    )
    assert response.status_code == 404


async def test_delete_missing_person_404(client, sessionmaker) -> None:
    headers = await _login(client, sessionmaker)
    response = await client.delete(f"/v1/people/{uuid.uuid4()}", headers=headers)
    assert response.status_code == 404


async def test_get_missing_calculation_404(client, sessionmaker) -> None:
    headers = await _login(client, sessionmaker)
    response = await client.get(f"/v1/calculations/{uuid.uuid4()}", headers=headers)
    assert response.status_code == 404


async def test_timing_missing_person_404(client, sessionmaker) -> None:
    headers = await _login(client, sessionmaker)
    response = await client.get(
        f"/v1/people/{uuid.uuid4()}/timing", params={"as_of_date": "2026-01-01"}, headers=headers
    )
    assert response.status_code == 404


async def test_create_calculation_missing_person_404(client, sessionmaker) -> None:
    headers = await _login(client, sessionmaker)
    response = await client.post(
        f"/v1/people/{uuid.uuid4()}/calculations",
        json={"as_of_date": "2026-01-01"},
        headers=headers,
    )
    assert response.status_code == 404


async def test_get_missing_relationship_404(client, sessionmaker) -> None:
    headers = await _login(client, sessionmaker)
    response = await client.get(f"/v1/relationships/{uuid.uuid4()}", headers=headers)
    assert response.status_code == 404


async def test_create_relationship_missing_calculation_404(client, sessionmaker) -> None:
    headers = await _login(client, sessionmaker)
    response = await client.post(
        "/v1/relationships",
        json={"calculation_a_id": str(uuid.uuid4()), "calculation_b_id": str(uuid.uuid4())},
        headers=headers,
    )
    assert response.status_code == 404


async def test_self_signup_when_enabled(db_engine) -> None:
    settings = Settings(
        database_url="postgresql+asyncpg://numra:numra_dev_password@127.0.0.1:5432/numra_test",
        environment="test",
        allow_self_signup=True,
    )
    app = create_app(settings=settings)
    app.state.engine = db_engine
    app.state.sessionmaker = build_sessionmaker(db_engine)

    from httpx import ASGITransport, AsyncClient

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        response = await ac.post(
            "/v1/auth/register",
            json={"email": "brandnew@example.com", "password": "abcdefgh12345"},
        )
        assert response.status_code == 201
        assert response.json()["email"] == "brandnew@example.com"


async def test_ready_reports_unhealthy_when_db_down() -> None:
    from numra_api.db import build_engine

    settings = Settings(
        database_url="postgresql+asyncpg://numra:wrong_password@127.0.0.1:5432/numra_test",
        environment="test",
    )
    app = create_app(settings=settings)
    bad_engine = build_engine(settings.database_url)
    app.state.engine = bad_engine
    app.state.sessionmaker = build_sessionmaker(bad_engine)

    from httpx import ASGITransport, AsyncClient

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        response = await ac.get("/v1/health/ready")
        assert response.status_code == 200
        assert response.json()["database"] == "unhealthy"
        assert response.json()["status"] == "unhealthy"
    await bad_engine.dispose()
