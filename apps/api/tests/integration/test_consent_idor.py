from __future__ import annotations

import pytest

from numra_api.auth.passwords import hash_password
from numra_api.repositories.users import create_user

pytestmark = pytest.mark.integration


async def _signup(client, sessionmaker, email: str) -> dict:
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
    """Leaves the active session as user B (the redeemer) when it returns."""
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


async def test_revoke_takes_effect_immediately_next_request(client, sessionmaker) -> None:
    workspace_id = await _connect(
        client,
        sessionmaker,
        "consent-idor-immediate-a@example.com",
        "consent-idor-immediate-b@example.com",
    )
    headers_a = await _switch_user(client, "consent-idor-immediate-a@example.com")

    before = await client.get(f"/v1/workspaces/{workspace_id}/consent", headers=headers_a)
    assert "CORE_NUMEROLOGY" in {g["scope"] for g in before.json()["granted_by_me"]}

    revoke = await client.post(
        f"/v1/workspaces/{workspace_id}/consent/revoke",
        json={"scope": "CORE_NUMEROLOGY"},
        headers=headers_a,
    )
    assert revoke.status_code == 200

    after = await client.get(f"/v1/workspaces/{workspace_id}/consent", headers=headers_a)
    active_scopes = {g["scope"] for g in after.json()["granted_by_me"] if g["revoked_at"] is None}
    assert "CORE_NUMEROLOGY" not in active_scopes


async def test_repeated_invite_accept_after_existing_connection_fails(client, sessionmaker) -> None:
    email_a = "consent-idor-repeat-a@example.com"
    email_b = "consent-idor-repeat-b@example.com"
    await _connect(client, sessionmaker, email_a, email_b)

    headers_a = await _switch_user(client, email_a)
    second_invitation = (
        await client.post("/v1/connections/invitations", json={"method": "LINK"}, headers=headers_a)
    ).json()
    headers_b = await _switch_user(client, email_b)
    response = await client.post(
        "/v1/connections/invitations/redeem",
        json={"token": second_invitation["token"]},
        headers=headers_b,
    )
    assert response.status_code == 409
    assert response.json()["code"] == "CONNECTION_ALREADY_EXISTS"


async def test_foreign_user_cannot_grant_or_revoke_or_read_workspace_consent(
    client, sessionmaker
) -> None:
    workspace_id = await _connect(
        client,
        sessionmaker,
        "consent-idor-foreign-a@example.com",
        "consent-idor-foreign-b@example.com",
    )
    headers_c = await _signup(client, sessionmaker, "consent-idor-foreign-c@example.com")

    read_response = await client.get(f"/v1/workspaces/{workspace_id}/consent", headers=headers_c)
    assert read_response.status_code == 404

    grant_response = await client.post(
        f"/v1/workspaces/{workspace_id}/consent/grant",
        json={"scope": "PRIVATE_JOURNAL"},
        headers=headers_c,
    )
    assert grant_response.status_code == 404

    revoke_response = await client.post(
        f"/v1/workspaces/{workspace_id}/consent/revoke",
        json={"scope": "CORE_NUMEROLOGY"},
        headers=headers_c,
    )
    assert revoke_response.status_code == 404


async def test_consent_from_wrong_workspace_not_treated_as_granted(client, sessionmaker) -> None:
    """User A has a workspace with B and a separate workspace with D -- consent granted
    in the A<->B workspace must never appear as granted in the A<->D workspace."""
    email_a = "consent-idor-multi-a@example.com"
    workspace_ab = await _connect(client, sessionmaker, email_a, "consent-idor-multi-b@example.com")

    headers_a = await _switch_user(client, email_a)
    invitation_ad = (
        await client.post("/v1/connections/invitations", json={"method": "LINK"}, headers=headers_a)
    ).json()
    headers_d = await _signup(client, sessionmaker, "consent-idor-multi-d@example.com")
    redeem_ad = await client.post(
        "/v1/connections/invitations/redeem",
        json={"token": invitation_ad["token"]},
        headers=headers_d,
    )
    assert redeem_ad.status_code == 201
    workspace_ad = redeem_ad.json()["workspace_id"]
    assert workspace_ad != workspace_ab

    headers_a = await _switch_user(client, email_a)
    grant_ab_only = await client.post(
        f"/v1/workspaces/{workspace_ab}/consent/grant",
        json={"scope": "PRIVATE_JOURNAL"},
        headers=headers_a,
    )
    assert grant_ab_only.status_code == 201

    consent_ad = (
        await client.get(f"/v1/workspaces/{workspace_ad}/consent", headers=headers_a)
    ).json()
    assert "PRIVATE_JOURNAL" not in {g["scope"] for g in consent_ad["granted_by_me"]}
