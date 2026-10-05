from __future__ import annotations

import pytest

from numra_api.auth.passwords import hash_password
from numra_api.models import FeatureFlag
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


async def _login(client, email: str, password: str) -> None:
    response = await client.post("/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200


async def test_non_admin_gets_403_on_flags_list(client, sessionmaker) -> None:
    await _seed_user(sessionmaker, "regular1@example.com", "correct horse battery staple")
    await _login(client, "regular1@example.com", "correct horse battery staple")

    response = await client.get("/v1/admin/flags")

    assert response.status_code == 403


async def test_admin_can_list_flags(client, sessionmaker) -> None:
    await _seed_user(
        sessionmaker, "admin-list@example.com", "correct horse battery staple", role=UserRole.ADMIN
    )
    await _login(client, "admin-list@example.com", "correct horse battery staple")

    response = await client.get("/v1/admin/flags")

    assert response.status_code == 200
    names = {row["name"] for row in response.json()["flags"]}
    assert names == {
        "v2_master",
        "connections",
        "relationship_workspaces",
        "checkins",
        "tasks",
        "copilot",
        "evidence_layer",
    }


async def test_admin_can_toggle_flag_and_cache_is_invalidated_immediately(
    client, sessionmaker, app
) -> None:
    await _seed_user(
        sessionmaker, "admin-toggle@example.com", "correct horse battery staple", role=UserRole.ADMIN
    )
    await _login(client, "admin-toggle@example.com", "correct horse battery staple")

    toggle_response = await client.patch(
        "/v1/admin/flags/checkins",
        json={"enabled": True},
        headers={"x-csrf-token": client.cookies["numra_csrf"]},
    )
    assert toggle_response.status_code == 204

    async with sessionmaker() as db:
        flag = await db.get(FeatureFlag, "checkins")
        assert flag.enabled is True

    # The cache must be invalidated synchronously by the route handler -- not just
    # eventually consistent after the TTL -- so the very next read already sees the
    # new value instead of a stale cached one.
    cached = await app.state.feature_flag_cache.get_all()
    assert cached["checkins"] is True


async def test_toggle_flag_records_audit_event(client, sessionmaker) -> None:
    await _seed_user(
        sessionmaker, "admin-audit@example.com", "correct horse battery staple", role=UserRole.ADMIN
    )
    await _login(client, "admin-audit@example.com", "correct horse battery staple")

    # The central `app`/`client` fixture seeds all seven flags True (see Task 3) --
    # explicitly set a known starting value here instead of relying on that default,
    # so this test documents and asserts its own precondition.
    async with sessionmaker() as db:
        flag = await db.get(FeatureFlag, "tasks")
        flag.enabled = False
        await db.commit()

    await client.patch(
        "/v1/admin/flags/tasks",
        json={"enabled": True},
        headers={"x-csrf-token": client.cookies["numra_csrf"]},
    )

    audit_response = await client.get("/v1/admin/audit?action=FEATURE_FLAG_CHANGED")
    assert audit_response.status_code == 200
    items = audit_response.json()["items"]
    assert len(items) == 1
    assert items[0]["safe_metadata"] == {"flag": "tasks", "from": False, "to": True}


async def test_toggle_unknown_flag_returns_404(client, sessionmaker) -> None:
    await _seed_user(
        sessionmaker, "admin-404@example.com", "correct horse battery staple", role=UserRole.ADMIN
    )
    await _login(client, "admin-404@example.com", "correct horse battery staple")

    response = await client.patch(
        "/v1/admin/flags/does_not_exist",
        json={"enabled": True},
        headers={"x-csrf-token": client.cookies["numra_csrf"]},
    )

    assert response.status_code == 404
