"""PR-V2-04: person_account_mode + relationship_type + Relationship Workspace
OVERVIEW/DUAL PROFILE (routes/relationship_workspaces.py,
services/relationship_workspace_service.py). Reuses the `_connect` two-user helper
pattern from test_consent.py.
"""

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
    """Leaves the active session as user B (the redeemer)."""
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


# ---------------------------------------------------------------------------
# person_account_mode
# ---------------------------------------------------------------------------


async def test_create_person_defaults_to_self(client, sessionmaker, lukas_payload) -> None:
    headers = await _signup(client, sessionmaker, "pam-default@example.com")
    response = await client.post("/v1/people", json=lukas_payload, headers=headers)
    assert response.status_code == 201
    assert response.json()["person_account_mode"] == "SELF"


async def test_second_self_person_is_conflict(client, sessionmaker, lukas_payload) -> None:
    headers = await _signup(client, sessionmaker, "pam-conflict@example.com")
    first = await client.post("/v1/people", json=lukas_payload, headers=headers)
    assert first.status_code == 201

    second_payload = {**lukas_payload, "birth_first_names": "Zweite"}
    second = await client.post("/v1/people", json=second_payload, headers=headers)
    assert second.status_code == 409
    assert second.json()["code"] == "AMBIGUOUS_SELF_PROFILE"


async def test_patch_managed_other_to_self_conflicts_with_existing_self(
    client, sessionmaker, lukas_payload
) -> None:
    headers = await _signup(client, sessionmaker, "pam-patch-conflict@example.com")
    self_person = (await client.post("/v1/people", json=lukas_payload, headers=headers)).json()
    assert self_person["person_account_mode"] == "SELF"

    managed_payload = {
        **lukas_payload,
        "birth_first_names": "Kind",
        "person_account_mode": "MANAGED_MINOR",
    }
    managed_person = (await client.post("/v1/people", json=managed_payload, headers=headers)).json()
    assert managed_person["person_account_mode"] == "MANAGED_MINOR"

    patch = await client.patch(
        f"/v1/people/{managed_person['id']}",
        json={"person_account_mode": "SELF"},
        headers=headers,
    )
    assert patch.status_code == 409
    assert patch.json()["code"] == "AMBIGUOUS_SELF_PROFILE"


# ---------------------------------------------------------------------------
# relationship_type PATCH
# ---------------------------------------------------------------------------


async def test_relationship_type_patch_visible_to_other_member(
    client, sessionmaker, lukas_payload
) -> None:
    workspace_id = await _connect(client, sessionmaker, "rt-a@example.com", "rt-b@example.com")
    headers_a = await _switch_user(client, "rt-a@example.com")

    patch = await client.patch(
        f"/v1/workspaces/{workspace_id}",
        json={"relationship_type": "PARTNER"},
        headers=headers_a,
    )
    assert patch.status_code == 200
    assert patch.json()["relationship_type"] == "PARTNER"

    headers_b = await _switch_user(client, "rt-b@example.com")
    overview = await client.get(f"/v1/workspaces/{workspace_id}", headers=headers_b)
    assert overview.status_code == 200
    assert overview.json()["workspace"]["relationship_type"] == "PARTNER"


async def test_relationship_type_patch_by_non_member_is_404(client, sessionmaker) -> None:
    workspace_id = await _connect(
        client, sessionmaker, "rt-nm-a@example.com", "rt-nm-b@example.com"
    )
    headers_stranger = await _signup(client, sessionmaker, "rt-nm-stranger@example.com")

    patch = await client.patch(
        f"/v1/workspaces/{workspace_id}",
        json={"relationship_type": "PARTNER"},
        headers=headers_stranger,
    )
    assert patch.status_code == 404


async def test_relationship_type_patch_on_dissolved_workspace_is_409(client, sessionmaker) -> None:
    workspace_id = await _connect(
        client, sessionmaker, "rt-diss-a@example.com", "rt-diss-b@example.com"
    )
    headers_b = await _switch_user(client, "rt-diss-b@example.com")

    connections = (await client.get("/v1/connections", headers=headers_b)).json()
    connection_id = connections[0]["id"]
    dissolve = await client.post(f"/v1/connections/{connection_id}/dissolve", headers=headers_b)
    assert dissolve.status_code == 200

    patch = await client.patch(
        f"/v1/workspaces/{workspace_id}",
        json={"relationship_type": "PARTNER"},
        headers=headers_b,
    )
    assert patch.status_code == 409
    assert patch.json()["code"] == "WORKSPACE_DISSOLVED"


# ---------------------------------------------------------------------------
# GET /v1/workspaces/{workspace_id} -- OVERVIEW + DUAL PROFILE
# ---------------------------------------------------------------------------


async def test_workspace_overview_dual_profile_both_members(
    client, sessionmaker, lukas_payload
) -> None:
    workspace_id = await _connect(client, sessionmaker, "ov-a@example.com", "ov-b@example.com")

    headers_a = await _switch_user(client, "ov-a@example.com")
    person_a = (await client.post("/v1/people", json=lukas_payload, headers=headers_a)).json()
    await client.post(
        f"/v1/people/{person_a['id']}/calculations",
        json={"as_of_date": "2026-01-01"},
        headers=headers_a,
    )

    headers_b = await _switch_user(client, "ov-b@example.com")
    other_payload = {**lukas_payload, "birth_first_names": "Anna", "birth_last_name": "Beispiel"}
    person_b = (await client.post("/v1/people", json=other_payload, headers=headers_b)).json()
    await client.post(
        f"/v1/people/{person_b['id']}/calculations",
        json={"as_of_date": "2026-01-01"},
        headers=headers_b,
    )

    overview_a = await client.get(f"/v1/workspaces/{workspace_id}", headers=headers_a)
    assert overview_a.status_code == 200
    body = overview_a.json()
    assert body["workspace"]["id"] == workspace_id
    assert len(body["dual_profile"]) == 2
    for member in body["dual_profile"]:
        assert member["self_person"] is not None
        assert member["core_numbers"] is not None
        assert "life_path" in member["core_numbers"]
        assert "personal_year" in member["core_numbers"]

    overview_b = await client.get(f"/v1/workspaces/{workspace_id}", headers=headers_b)
    assert overview_b.status_code == 200


async def test_workspace_overview_foreign_user_is_404(client, sessionmaker) -> None:
    workspace_id = await _connect(
        client, sessionmaker, "ov-fu-a@example.com", "ov-fu-b@example.com"
    )
    headers_stranger = await _signup(client, sessionmaker, "ov-fu-stranger@example.com")

    response = await client.get(f"/v1/workspaces/{workspace_id}", headers=headers_stranger)
    assert response.status_code == 404


async def test_workspace_overview_after_dissolve_still_readable(client, sessionmaker) -> None:
    workspace_id = await _connect(
        client, sessionmaker, "ov-diss-a@example.com", "ov-diss-b@example.com"
    )
    headers_b = await _switch_user(client, "ov-diss-b@example.com")
    connections = (await client.get("/v1/connections", headers=headers_b)).json()
    connection_id = connections[0]["id"]
    await client.post(f"/v1/connections/{connection_id}/dissolve", headers=headers_b)

    overview = await client.get(f"/v1/workspaces/{workspace_id}", headers=headers_b)
    assert overview.status_code == 200
    assert overview.json()["workspace"]["status"] == "DISSOLVED"


async def test_workspace_overview_self_person_missing_is_null_not_500(client, sessionmaker) -> None:
    workspace_id = await _connect(
        client, sessionmaker, "ov-nop-a@example.com", "ov-nop-b@example.com"
    )
    headers_a = await _switch_user(client, "ov-nop-a@example.com")

    overview = await client.get(f"/v1/workspaces/{workspace_id}", headers=headers_a)
    assert overview.status_code == 200
    for member in overview.json()["dual_profile"]:
        assert member["self_person"] is None
        assert member["core_numbers"] is None


async def test_workspace_overview_consent_revoke_hides_only_revoking_side(
    client, sessionmaker, lukas_payload
) -> None:
    workspace_id = await _connect(
        client, sessionmaker, "ov-rev-a@example.com", "ov-rev-b@example.com"
    )

    headers_a = await _switch_user(client, "ov-rev-a@example.com")
    person_a = (await client.post("/v1/people", json=lukas_payload, headers=headers_a)).json()
    await client.post(
        f"/v1/people/{person_a['id']}/calculations",
        json={"as_of_date": "2026-01-01"},
        headers=headers_a,
    )

    headers_b = await _switch_user(client, "ov-rev-b@example.com")
    other_payload = {**lukas_payload, "birth_first_names": "Anna", "birth_last_name": "Beispiel"}
    person_b = (await client.post("/v1/people", json=other_payload, headers=headers_b)).json()
    await client.post(
        f"/v1/people/{person_b['id']}/calculations",
        json={"as_of_date": "2026-01-01"},
        headers=headers_b,
    )

    # A revokes CORE_NUMEROLOGY towards B.
    headers_a = await _switch_user(client, "ov-rev-a@example.com")
    revoke = await client.post(
        f"/v1/workspaces/{workspace_id}/consent/revoke",
        json={"scope": "CORE_NUMEROLOGY"},
        headers=headers_a,
    )
    assert revoke.status_code == 200

    # B's GET no longer shows A's core_numbers, but B still sees their own.
    headers_b = await _switch_user(client, "ov-rev-b@example.com")
    overview_b = await client.get(f"/v1/workspaces/{workspace_id}", headers=headers_b)
    assert overview_b.status_code == 200
    by_user = {m["user_id"]: m for m in overview_b.json()["dual_profile"]}
    async with sessionmaker() as db:
        from sqlalchemy import select

        from numra_api.models import User

        user_a_id = str(
            (
                await db.execute(select(User.id).where(User.email == "ov-rev-a@example.com"))
            ).scalar_one()
        )
        user_b_id = str(
            (
                await db.execute(select(User.id).where(User.email == "ov-rev-b@example.com"))
            ).scalar_one()
        )
    assert by_user[user_a_id]["core_numbers"] is None
    assert by_user[user_b_id]["core_numbers"] is not None
    # Regression: self_person (id + real birth-name-derived display name) must be
    # gated by the same consent check as core_numbers -- revoking CORE_NUMEROLOGY
    # must not still leak A's Person identity/name to B.
    assert by_user[user_a_id]["self_person"] is None
    assert by_user[user_b_id]["self_person"] is not None

    # A still sees B's numbers (A never revoked B's grant to A).
    headers_a = await _switch_user(client, "ov-rev-a@example.com")
    overview_a = await client.get(f"/v1/workspaces/{workspace_id}", headers=headers_a)
    by_user_a = {m["user_id"]: m for m in overview_a.json()["dual_profile"]}
    assert by_user_a[user_b_id]["core_numbers"] is not None
    assert by_user_a[user_b_id]["self_person"] is not None
