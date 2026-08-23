from __future__ import annotations

import pytest

from numra_api.auth.passwords import hash_password
from numra_api.models.enums import UserRole
from numra_api.repositories.users import create_user, set_user_role

pytestmark = pytest.mark.integration


async def _seed_user(sessionmaker, email: str, password: str, *, role: UserRole = UserRole.USER):
    async with sessionmaker() as db:
        user = await create_user(db, email=email, password_hash=hash_password(password))
        if role != UserRole.USER:
            await set_user_role(db, user=user, role=role)
        await db.commit()
        return user


async def _login(client, email: str, password: str):
    response = await client.post("/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return response.json()


async def test_disable_revokes_target_session_and_records_audit(client, sessionmaker, app) -> None:
    await _seed_user(
        sessionmaker, "admin1@example.com", "correct horse battery staple", role=UserRole.ADMIN
    )
    target = await _seed_user(sessionmaker, "target1@example.com", "correct horse battery staple")

    # Log the target in with a separate client sharing the same app/db, to obtain a
    # live session cookie for that account without disturbing the admin's own client.
    from httpx import ASGITransport, AsyncClient

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as target_client:
        target_login = await target_client.post(
            "/v1/auth/login",
            json={"email": "target1@example.com", "password": "correct horse battery staple"},
        )
        assert target_login.status_code == 200

        await _login(client, "admin1@example.com", "correct horse battery staple")
        disable_response = await client.post(
            f"/v1/admin/users/{target.id}/disable",
            headers={"x-csrf-token": client.cookies["numra_csrf"]},
        )
        assert disable_response.status_code == 204

        # The target's previously-valid session is now rejected -- generic 401, same
        # shape as "no session" (anti-enumeration).
        me_after = await target_client.get("/v1/auth/me")
        assert me_after.status_code == 401
        assert me_after.json()["code"] == "NOT_AUTHENTICATED"

    audit_response = await client.get(f"/v1/admin/audit?target_user_id={target.id}")
    assert audit_response.status_code == 200
    actions = [e["action"] for e in audit_response.json()["items"]]
    assert "USER_DISABLED" in actions


async def test_admin_cannot_disable_self(client, sessionmaker) -> None:
    admin = await _seed_user(
        sessionmaker, "admin2@example.com", "correct horse battery staple", role=UserRole.ADMIN
    )
    await _login(client, "admin2@example.com", "correct horse battery staple")

    response = await client.post(
        f"/v1/admin/users/{admin.id}/disable",
        headers={"x-csrf-token": client.cookies["numra_csrf"]},
    )
    assert response.status_code == 403

    me_response = await client.get("/v1/auth/me")
    assert me_response.status_code == 200


async def test_disable_without_csrf_rejected(client, sessionmaker) -> None:
    await _seed_user(
        sessionmaker, "admin3@example.com", "correct horse battery staple", role=UserRole.ADMIN
    )
    target = await _seed_user(sessionmaker, "target3@example.com", "correct horse battery staple")
    await _login(client, "admin3@example.com", "correct horse battery staple")

    response = await client.post(f"/v1/admin/users/{target.id}/disable")
    assert response.status_code == 403
    assert response.json()["code"] == "CSRF_VALIDATION_FAILED"


async def test_enable_reverses_disable(client, sessionmaker) -> None:
    await _seed_user(
        sessionmaker, "admin4@example.com", "correct horse battery staple", role=UserRole.ADMIN
    )
    target = await _seed_user(sessionmaker, "target4@example.com", "correct horse battery staple")
    await _login(client, "admin4@example.com", "correct horse battery staple")

    await client.post(
        f"/v1/admin/users/{target.id}/disable",
        headers={"x-csrf-token": client.cookies["numra_csrf"]},
    )
    enable_response = await client.post(
        f"/v1/admin/users/{target.id}/enable",
        headers={"x-csrf-token": client.cookies["numra_csrf"]},
    )
    assert enable_response.status_code == 204

    view_response = await client.get(f"/v1/admin/users/{target.id}")
    assert view_response.status_code == 200
    assert view_response.json()["is_active"] is True
