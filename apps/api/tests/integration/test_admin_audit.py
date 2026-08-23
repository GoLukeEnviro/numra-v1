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


async def _login(client, email: str, password: str) -> None:
    response = await client.post("/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200


async def test_audit_entries_created_per_action_and_filterable(client, sessionmaker) -> None:
    await _seed_user(
        sessionmaker, "auditadmin@example.com", "correct horse battery staple", role=UserRole.ADMIN
    )
    target = await _seed_user(
        sessionmaker, "audittarget@example.com", "correct horse battery staple"
    )
    await _login(client, "auditadmin@example.com", "correct horse battery staple")
    csrf = client.cookies["numra_csrf"]

    await client.post(f"/v1/admin/users/{target.id}/disable", headers={"x-csrf-token": csrf})
    await client.post(f"/v1/admin/users/{target.id}/enable", headers={"x-csrf-token": csrf})
    await client.post(
        f"/v1/admin/users/{target.id}/revoke-sessions", headers={"x-csrf-token": csrf}
    )

    all_events = await client.get("/v1/admin/audit")
    assert all_events.status_code == 200
    actions = [e["action"] for e in all_events.json()["items"]]
    assert "USER_DISABLED" in actions
    assert "USER_ENABLED" in actions
    assert "USER_SESSIONS_REVOKED" in actions

    filtered = await client.get("/v1/admin/audit", params={"action": "USER_DISABLED"})
    assert filtered.status_code == 200
    assert all(e["action"] == "USER_DISABLED" for e in filtered.json()["items"])
    assert len(filtered.json()["items"]) >= 1

    by_target = await client.get("/v1/admin/audit", params={"target_user_id": str(target.id)})
    assert by_target.status_code == 200
    assert all(e["target_user_id"] == str(target.id) for e in by_target.json()["items"])
