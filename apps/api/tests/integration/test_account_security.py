from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from numra_api.auth.passwords import hash_password
from numra_api.repositories.users import create_user

pytestmark = pytest.mark.integration


async def _seed_user(sessionmaker, email: str, password: str) -> None:
    async with sessionmaker() as db:
        await create_user(db, email=email, password_hash=hash_password(password))
        await db.commit()


async def _login(client, email: str, password: str) -> dict:
    response = await client.post("/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return {"x-csrf-token": client.cookies["numra_csrf"]}


async def test_change_password_requires_current_password(client, sessionmaker) -> None:
    await _seed_user(sessionmaker, "change-pw@example.com", "correct horse battery staple")
    headers = await _login(client, "change-pw@example.com", "correct horse battery staple")

    wrong = await client.post(
        "/v1/auth/change-password",
        json={"current_password": "totally-wrong", "new_password": "a-new-password-123"},
        headers=headers,
    )
    assert wrong.status_code == 401
    assert wrong.json()["code"] == "INVALID_CREDENTIALS"


async def test_change_password_rejects_short_new_password(client, sessionmaker) -> None:
    await _seed_user(sessionmaker, "short-new-pw@example.com", "correct horse battery staple")
    headers = await _login(client, "short-new-pw@example.com", "correct horse battery staple")

    response = await client.post(
        "/v1/auth/change-password",
        json={"current_password": "correct horse battery staple", "new_password": "short1"},
        headers=headers,
    )
    assert response.status_code == 422


async def test_change_password_succeeds_and_old_password_stops_working(
    client, sessionmaker
) -> None:
    await _seed_user(sessionmaker, "rotate-pw@example.com", "correct horse battery staple")
    headers = await _login(client, "rotate-pw@example.com", "correct horse battery staple")

    response = await client.post(
        "/v1/auth/change-password",
        json={
            "current_password": "correct horse battery staple",
            "new_password": "a-brand-new-password-1",
        },
        headers=headers,
    )
    assert response.status_code == 204

    # The session making the change stays valid -- not logged out by its own request.
    me_response = await client.get("/v1/auth/me")
    assert me_response.status_code == 200

    old_login = await client.post(
        "/v1/auth/login",
        json={"email": "rotate-pw@example.com", "password": "correct horse battery staple"},
    )
    assert old_login.status_code == 401

    new_login = await client.post(
        "/v1/auth/login",
        json={"email": "rotate-pw@example.com", "password": "a-brand-new-password-1"},
    )
    assert new_login.status_code == 200


async def test_change_password_revokes_other_sessions_but_keeps_the_current_one(
    client, app, sessionmaker
) -> None:
    """The device making the password change stays signed in; every other device is
    signed out (V1.5 Epic N)."""
    await _seed_user(sessionmaker, "multi-device@example.com", "correct horse battery staple")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as other_device:
        await _login(other_device, "multi-device@example.com", "correct horse battery staple")
        assert (await other_device.get("/v1/auth/me")).status_code == 200

        headers = await _login(client, "multi-device@example.com", "correct horse battery staple")
        change_response = await client.post(
            "/v1/auth/change-password",
            json={
                "current_password": "correct horse battery staple",
                "new_password": "a-brand-new-password-1",
            },
            headers=headers,
        )
        assert change_response.status_code == 204

        # This device (the one that changed the password) is still signed in.
        assert (await client.get("/v1/auth/me")).status_code == 200
        # The other device's session was revoked.
        assert (await other_device.get("/v1/auth/me")).status_code == 401


async def test_list_sessions_marks_the_calling_session_as_current(
    client, app, sessionmaker
) -> None:
    await _seed_user(sessionmaker, "list-sessions@example.com", "correct horse battery staple")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as other_device:
        await _login(other_device, "list-sessions@example.com", "correct horse battery staple")
        await _login(client, "list-sessions@example.com", "correct horse battery staple")

        response = await client.get("/v1/auth/sessions")
        assert response.status_code == 200
        sessions = response.json()
        assert len(sessions) == 2
        current = [s for s in sessions if s["is_current"]]
        assert len(current) == 1
        # No IP address or device identifier is ever present.
        for session in sessions:
            assert set(session.keys()) == {"id", "created_at", "expires_at", "is_current"}


async def test_revoke_other_sessions_signs_out_every_other_device(
    client, app, sessionmaker
) -> None:
    await _seed_user(sessionmaker, "revoke-others@example.com", "correct horse battery staple")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as other_device:
        await _login(other_device, "revoke-others@example.com", "correct horse battery staple")
        headers = await _login(client, "revoke-others@example.com", "correct horse battery staple")

        response = await client.post("/v1/auth/sessions/revoke-others", headers=headers)
        assert response.status_code == 204

        assert (await client.get("/v1/auth/me")).status_code == 200
        assert (await other_device.get("/v1/auth/me")).status_code == 401


async def test_system_info_excludes_secrets(client, sessionmaker) -> None:
    await _seed_user(sessionmaker, "system-info@example.com", "correct horse battery staple")
    headers = await _login(client, "system-info@example.com", "correct horse battery staple")

    response = await client.get("/v1/system-info", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {
        "environment",
        "app_timezone",
        "session_ttl_hours",
        "self_signup_enabled",
        "llm_provider",
        "pdf_export_enabled",
    }
    dumped = str(body)
    assert "insecure" not in dumped.lower()
    assert "secret" not in dumped.lower()
    assert "token" not in dumped.lower()


async def test_system_info_requires_authentication(client) -> None:
    response = await client.get("/v1/system-info")
    assert response.status_code == 401
