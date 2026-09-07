from __future__ import annotations

import pytest

from numra_api.auth.passwords import hash_password
from numra_api.repositories.users import create_user

pytestmark = pytest.mark.integration


async def _login(client, sessionmaker, email: str) -> None:
    async with sessionmaker() as db:
        await create_user(db, email=email, password_hash=hash_password("password12345"))
        await db.commit()
    response = await client.post(
        "/v1/auth/login", json={"email": email, "password": "password12345"}
    )
    assert response.status_code == 200


async def test_get_entitlements_requires_auth(client) -> None:
    response = await client.get("/v1/me/entitlements")
    assert response.status_code == 401


async def test_get_entitlements_resolves_beta_default_without_explicit_assignment(
    client, sessionmaker
) -> None:
    """The migration seeds exactly the "beta_default" `EntitlementSet` (see
    alembic/versions) and no `EntitlementAssignment` for a freshly registered user --
    this must resolve every flag to true and every limit to unlimited (None) via the
    fallback path in repositories/entitlements.py."""
    await _login(client, sessionmaker, "entitlements-default@example.com")

    response = await client.get("/v1/me/entitlements")

    assert response.status_code == 200
    assert response.json() == {
        "personal_workspace": True,
        "connections": True,
        "relationship_workspaces": True,
        "relationship_checkins": True,
        "relationship_copilot": True,
        "advanced_relationship_analysis": True,
        "life_tracking": True,
        "premium_reports": True,
        "max_connections": None,
        "max_workspaces": None,
    }
