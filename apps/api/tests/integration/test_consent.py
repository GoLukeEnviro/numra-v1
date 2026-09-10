from __future__ import annotations

import pytest
from sqlalchemy import select

from numra_api.auth.passwords import hash_password
from numra_api.models import ConsentEvent, ConsentGrant
from numra_api.repositories.users import create_user
from numra_api.services.consent_service import assert_consent
from numra_api.services.errors import ConsentNotGranted

pytestmark = pytest.mark.integration


async def _signup(client, sessionmaker, email: str) -> dict:
    """Creates the user and logs in -- use once per email. See `_switch_user` to
    re-activate an already-created user's session (the test `client` fixture has one
    shared cookie jar, so only one user is "logged in" at a time)."""
    async with sessionmaker() as db:
        await create_user(db, email=email, password_hash=hash_password("password12345"))
        await db.commit()
    return await _switch_user(client, email)


async def _switch_user(client, email: str) -> dict:
    await client.post("/v1/auth/logout")
    response = await client.post(
        "/v1/auth/login", json={"email": email, "password": "password12345"}
    )
    assert response.status_code == 200
    return {"x-csrf-token": client.cookies["numra_csrf"]}


async def _connect(client, sessionmaker, email_a: str, email_b: str) -> str:
    """Leaves the active session as user B (the redeemer) when it returns. Callers
    use `_switch_user` to reactivate A or B by email as needed."""
    headers_a = await _signup(client, sessionmaker, email_a)
    invitation = (
        await client.post("/v1/connections/invitations", json={"method": "LINK"}, headers=headers_a)
    ).json()
    headers_b = await _signup(client, sessionmaker, email_b)
    redeem = await client.post(
        "/v1/connections/invitations/redeem",
        json={"token": invitation["token"]},
        headers=headers_b,
    )
    assert redeem.status_code == 201
    return redeem.json()["workspace_id"]


async def test_default_grants_correct_directions_and_scopes(client, sessionmaker) -> None:
    workspace_id = await _connect(
        client, sessionmaker, "consent-def-a@example.com", "consent-def-b@example.com"
    )
    headers_a = await _switch_user(client, "consent-def-a@example.com")

    consent_a = await client.get(f"/v1/workspaces/{workspace_id}/consent", headers=headers_a)
    assert consent_a.status_code == 200
    body_a = consent_a.json()
    assert {g["scope"] for g in body_a["granted_by_me"]} == {
        "CORE_NUMEROLOGY",
        "RELATIONSHIP_INSIGHTS",
        "CURRENT_TIMING",
    }
    assert {g["scope"] for g in body_a["granted_to_me"]} == {
        "CORE_NUMEROLOGY",
        "RELATIONSHIP_INSIGHTS",
        "CURRENT_TIMING",
    }
    # No non-default scope was auto-granted.
    all_scopes = {g["scope"] for g in body_a["granted_by_me"] + body_a["granted_to_me"]}
    assert "PRIVATE_JOURNAL" not in all_scopes
    assert "PRIVATE_TASKS" not in all_scopes
    assert "PRIVATE_COPILOT" not in all_scopes
    assert "OTHER_RELATIONSHIPS" not in all_scopes
    assert "LIFE_TRACKING" not in all_scopes


async def test_directional_grant_and_event_recorded(client, sessionmaker) -> None:
    workspace_id = await _connect(
        client, sessionmaker, "consent-dir-a@example.com", "consent-dir-b@example.com"
    )
    headers_a = await _switch_user(client, "consent-dir-a@example.com")

    response = await client.post(
        f"/v1/workspaces/{workspace_id}/consent/grant",
        json={"scope": "PRIVATE_JOURNAL"},
        headers=headers_a,
    )
    assert response.status_code == 201
    grant = response.json()
    assert grant["scope"] == "PRIVATE_JOURNAL"

    async with sessionmaker() as db:
        events = (
            (await db.execute(select(ConsentEvent).where(ConsentEvent.grant_id == grant["id"])))
            .scalars()
            .all()
        )
        assert len(events) == 1
        assert events[0].event_type == "GRANTED"

    # The other direction must still be ungranted.
    headers_b = await _switch_user(client, "consent-dir-b@example.com")
    consent_b = (
        await client.get(f"/v1/workspaces/{workspace_id}/consent", headers=headers_b)
    ).json()
    assert "PRIVATE_JOURNAL" not in {g["scope"] for g in consent_b["granted_by_me"]}


async def test_revoke_writes_event_and_clears_grant(client, sessionmaker) -> None:
    workspace_id = await _connect(
        client, sessionmaker, "consent-rev-a@example.com", "consent-rev-b@example.com"
    )
    headers_a = await _switch_user(client, "consent-rev-a@example.com")

    revoke = await client.post(
        f"/v1/workspaces/{workspace_id}/consent/revoke",
        json={"scope": "CORE_NUMEROLOGY"},
        headers=headers_a,
    )
    assert revoke.status_code == 200
    grant_id = revoke.json()["id"]
    assert revoke.json()["revoked_at"] is not None

    async with sessionmaker() as db:
        events = (
            (await db.execute(select(ConsentEvent).where(ConsentEvent.grant_id == grant_id)))
            .scalars()
            .all()
        )
        event_types = {e.event_type for e in events}
        assert "REVOKED" in event_types

    consent_a = (
        await client.get(f"/v1/workspaces/{workspace_id}/consent", headers=headers_a)
    ).json()
    assert "CORE_NUMEROLOGY" not in {
        g["scope"] for g in consent_a["granted_by_me"] if g["revoked_at"] is None
    }


async def test_regrant_after_revoke_reactivates_same_grant(client, sessionmaker) -> None:
    workspace_id = await _connect(
        client, sessionmaker, "consent-regrant-a@example.com", "consent-regrant-b@example.com"
    )
    headers_a = await _switch_user(client, "consent-regrant-a@example.com")
    path = f"/v1/workspaces/{workspace_id}/consent"

    first = await client.post(f"{path}/grant", json={"scope": "PRIVATE_JOURNAL"}, headers=headers_a)
    assert first.status_code == 201
    grant_id = first.json()["id"]

    revoke = await client.post(
        f"{path}/revoke", json={"scope": "PRIVATE_JOURNAL"}, headers=headers_a
    )
    assert revoke.status_code == 200
    assert revoke.json()["id"] == grant_id

    regrant = await client.post(
        f"{path}/grant", json={"scope": "PRIVATE_JOURNAL"}, headers=headers_a
    )
    assert regrant.status_code == 201
    assert regrant.json()["id"] == grant_id
    assert regrant.json()["revoked_at"] is None

    async with sessionmaker() as db:
        events = (
            (await db.execute(select(ConsentEvent).where(ConsentEvent.grant_id == grant_id)))
            .scalars()
            .all()
        )
        ordered = [e.event_type for e in sorted(events, key=lambda e: e.occurred_at)]
        assert len(ordered) == 3
        assert ordered.count("GRANTED") == 2
        assert ordered.count("REVOKED") == 1
        assert ordered[0] == "GRANTED"
        assert ordered[-1] == "GRANTED"
        grant = (
            await db.execute(select(ConsentGrant).where(ConsentGrant.id == grant_id))
        ).scalar_one()
        # assert_consent passes again for the grantee after the re-grant.
        await assert_consent(
            db,
            workspace_id=workspace_id,
            grantor_user_id=grant.grantor_user_id,
            grantee_user_id=grant.grantee_user_id,
            scope="PRIVATE_JOURNAL",
        )


async def test_regrant_leaves_opposite_direction_independent(client, sessionmaker) -> None:
    workspace_id = await _connect(
        client, sessionmaker, "consent-regdir-a@example.com", "consent-regdir-b@example.com"
    )
    path = f"/v1/workspaces/{workspace_id}/consent"

    headers_a = await _switch_user(client, "consent-regdir-a@example.com")
    grant_a = await client.post(
        f"{path}/grant", json={"scope": "PRIVATE_JOURNAL"}, headers=headers_a
    )
    await client.post(f"{path}/revoke", json={"scope": "PRIVATE_JOURNAL"}, headers=headers_a)
    regrant_a = await client.post(
        f"{path}/grant", json={"scope": "PRIVATE_JOURNAL"}, headers=headers_a
    )
    assert regrant_a.json()["id"] == grant_a.json()["id"]

    headers_b = await _switch_user(client, "consent-regdir-b@example.com")
    grant_b = await client.post(
        f"{path}/grant", json={"scope": "PRIVATE_JOURNAL"}, headers=headers_b
    )
    assert grant_b.status_code == 201
    assert grant_b.json()["id"] != grant_a.json()["id"]

    headers_a = await _switch_user(client, "consent-regdir-a@example.com")
    consent_a = (await client.get(path, headers=headers_a)).json()
    active_by_a = {g["scope"] for g in consent_a["granted_by_me"] if g["revoked_at"] is None}
    assert "PRIVATE_JOURNAL" in active_by_a


async def test_grant_on_active_scope_is_idempotent(client, sessionmaker) -> None:
    workspace_id = await _connect(
        client, sessionmaker, "consent-idem-a@example.com", "consent-idem-b@example.com"
    )
    headers_a = await _switch_user(client, "consent-idem-a@example.com")
    path = f"/v1/workspaces/{workspace_id}/consent"

    first = await client.post(f"{path}/grant", json={"scope": "CORE_NUMEROLOGY"}, headers=headers_a)
    second = await client.post(
        f"{path}/grant", json={"scope": "CORE_NUMEROLOGY"}, headers=headers_a
    )
    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["id"] == second.json()["id"]
    assert second.json()["revoked_at"] is None

    async with sessionmaker() as db:
        granted_events = (
            (
                await db.execute(
                    select(ConsentEvent).where(
                        ConsentEvent.grant_id == first.json()["id"],
                        ConsentEvent.event_type == "GRANTED",
                    )
                )
            )
            .scalars()
            .all()
        )
        # Only the single GRANTED event from the workspace's default auto-grant --
        # the two idempotent re-grants add nothing.
        assert len(granted_events) == 1


async def test_assert_consent_fails_after_revoke_without_regrant(client, sessionmaker) -> None:
    workspace_id = await _connect(
        client, sessionmaker, "consent-arev-a@example.com", "consent-arev-b@example.com"
    )
    headers_a = await _switch_user(client, "consent-arev-a@example.com")
    path = f"/v1/workspaces/{workspace_id}/consent"

    grant = (
        await client.post(f"{path}/grant", json={"scope": "PRIVATE_JOURNAL"}, headers=headers_a)
    ).json()
    await client.post(f"{path}/revoke", json={"scope": "PRIVATE_JOURNAL"}, headers=headers_a)

    async with sessionmaker() as db:
        row = (
            await db.execute(select(ConsentGrant).where(ConsentGrant.id == grant["id"]))
        ).scalar_one()
        with pytest.raises(ConsentNotGranted):
            await assert_consent(
                db,
                workspace_id=workspace_id,
                grantor_user_id=row.grantor_user_id,
                grantee_user_id=row.grantee_user_id,
                scope="PRIVATE_JOURNAL",
            )


async def test_only_grantor_can_revoke(client, sessionmaker) -> None:
    workspace_id = await _connect(
        client, sessionmaker, "consent-only-a@example.com", "consent-only-b@example.com"
    )
    headers_b = await _switch_user(client, "consent-only-b@example.com")

    # B tries to revoke a scope that only A granted to B (A is grantor) -- B is not
    # the grantor for that direction and must not be able to revoke it via B's own
    # grantor_user_id (the endpoint always uses the caller as grantor).
    response = await client.post(
        f"/v1/workspaces/{workspace_id}/consent/revoke",
        json={"scope": "PRIVATE_JOURNAL"},
        headers=headers_b,
    )
    assert response.status_code == 403
    assert response.json()["code"] == "CONSENT_NOT_GRANTED"
