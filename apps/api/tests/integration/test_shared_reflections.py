"""PR-V2-08 -- Shared Reflection (routes/shared_reflections.py,
routes/private_reflections.py::share_private_reflection_route,
services/shared_reflection_service.py). Reuses the `_connect` two-user helper
pattern from test_workspace_tasks.py / test_relationship_roadmaps.py.
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


async def _create_person(client, headers, lukas_payload) -> str:
    response = await client.post("/v1/people", json=lukas_payload, headers=headers)
    assert response.status_code == 201
    return response.json()["id"]


async def _create_private_reflection(
    client, headers, person_id, content="Heute war ein guter Tag."
):
    response = await client.post(
        f"/v1/people/{person_id}/private-reflections",
        json={"entry_date": "2026-08-19", "content": content},
        headers=headers,
    )
    assert response.status_code == 201
    return response.json()


# ---------------------------------------------------------------------------
# Share flow -- snapshot, not a live link
# ---------------------------------------------------------------------------


async def test_share_creates_snapshot(client, sessionmaker, lukas_payload) -> None:
    workspace_id = await _connect(client, sessionmaker, "sh-a@example.com", "sh-b@example.com")
    headers_a = await _switch_user(client, "sh-a@example.com")
    person_id = await _create_person(client, headers_a, lukas_payload)
    reflection = await _create_private_reflection(client, headers_a, person_id, "Original content")

    share = await client.post(
        f"/v1/private-reflections/{reflection['id']}/share",
        json={"workspace_id": workspace_id},
        headers=headers_a,
    )
    assert share.status_code == 201
    shared = share.json()
    assert shared["content"] == "Original content"
    assert shared["entry_date"] == "2026-08-19"
    assert shared["source_private_reflection_id"] == reflection["id"]

    # Visible to the other member.
    headers_b = await _switch_user(client, "sh-b@example.com")
    get_b = await client.get(
        f"/v1/workspaces/{workspace_id}/shared-reflections/{shared['id']}", headers=headers_b
    )
    assert get_b.status_code == 200
    assert get_b.json()["content"] == "Original content"


async def test_later_edit_of_source_does_not_change_shared_snapshot(
    client, sessionmaker, lukas_payload
) -> None:
    workspace_id = await _connect(client, sessionmaker, "edit-a@example.com", "edit-b@example.com")
    headers_a = await _switch_user(client, "edit-a@example.com")
    person_id = await _create_person(client, headers_a, lukas_payload)
    reflection = await _create_private_reflection(client, headers_a, person_id, "Before edit")

    share = await client.post(
        f"/v1/private-reflections/{reflection['id']}/share",
        json={"workspace_id": workspace_id},
        headers=headers_a,
    )
    shared_id = share.json()["id"]

    patch = await client.patch(
        f"/v1/private-reflections/{reflection['id']}",
        json={"content": "After edit"},
        headers=headers_a,
    )
    assert patch.status_code == 200

    get_shared = await client.get(
        f"/v1/workspaces/{workspace_id}/shared-reflections/{shared_id}", headers=headers_a
    )
    assert get_shared.json()["content"] == "Before edit"


async def test_later_delete_of_source_does_not_delete_shared_snapshot(
    client, sessionmaker, lukas_payload
) -> None:
    workspace_id = await _connect(client, sessionmaker, "del-a@example.com", "del-b@example.com")
    headers_a = await _switch_user(client, "del-a@example.com")
    person_id = await _create_person(client, headers_a, lukas_payload)
    reflection = await _create_private_reflection(client, headers_a, person_id, "Will be deleted")

    share = await client.post(
        f"/v1/private-reflections/{reflection['id']}/share",
        json={"workspace_id": workspace_id},
        headers=headers_a,
    )
    shared_id = share.json()["id"]

    delete = await client.delete(f"/v1/private-reflections/{reflection['id']}", headers=headers_a)
    assert delete.status_code == 204

    get_shared = await client.get(
        f"/v1/workspaces/{workspace_id}/shared-reflections/{shared_id}", headers=headers_a
    )
    assert get_shared.status_code == 200
    assert get_shared.json()["content"] == "Will be deleted"
    assert get_shared.json()["source_private_reflection_id"] is None


async def test_share_foreign_private_reflection_is_404(client, sessionmaker, lukas_payload) -> None:
    workspace_id = await _connect(client, sessionmaker, "for-a@example.com", "for-b@example.com")
    headers_a = await _switch_user(client, "for-a@example.com")
    person_id = await _create_person(client, headers_a, lukas_payload)
    reflection = await _create_private_reflection(client, headers_a, person_id)

    headers_b = await _switch_user(client, "for-b@example.com")
    share = await client.post(
        f"/v1/private-reflections/{reflection['id']}/share",
        json={"workspace_id": workspace_id},
        headers=headers_b,
    )
    assert share.status_code == 404


# ---------------------------------------------------------------------------
# Unshare -- only the author may DELETE
# ---------------------------------------------------------------------------


async def test_unshare_only_by_author(client, sessionmaker, lukas_payload) -> None:
    workspace_id = await _connect(client, sessionmaker, "un-a@example.com", "un-b@example.com")
    headers_a = await _switch_user(client, "un-a@example.com")
    person_id = await _create_person(client, headers_a, lukas_payload)
    reflection = await _create_private_reflection(client, headers_a, person_id)
    shared_id = (
        await client.post(
            f"/v1/private-reflections/{reflection['id']}/share",
            json={"workspace_id": workspace_id},
            headers=headers_a,
        )
    ).json()["id"]

    headers_b = await _switch_user(client, "un-b@example.com")
    partner_delete = await client.delete(
        f"/v1/workspaces/{workspace_id}/shared-reflections/{shared_id}", headers=headers_b
    )
    assert partner_delete.status_code == 404

    headers_a = await _switch_user(client, "un-a@example.com")
    author_delete = await client.delete(
        f"/v1/workspaces/{workspace_id}/shared-reflections/{shared_id}", headers=headers_a
    )
    assert author_delete.status_code == 204


# ---------------------------------------------------------------------------
# IDOR
# ---------------------------------------------------------------------------


async def test_non_member_gets_404_on_all_shared_reflection_routes(
    client, sessionmaker, lukas_payload
) -> None:
    workspace_id = await _connect(client, sessionmaker, "idor-a@example.com", "idor-b@example.com")
    headers_a = await _switch_user(client, "idor-a@example.com")
    person_id = await _create_person(client, headers_a, lukas_payload)
    reflection = await _create_private_reflection(client, headers_a, person_id)
    shared = (
        await client.post(
            f"/v1/private-reflections/{reflection['id']}/share",
            json={"workspace_id": workspace_id},
            headers=headers_a,
        )
    ).json()

    headers_c = await _signup(client, sessionmaker, "idor-c@example.com")

    responses = [
        await client.get(f"/v1/workspaces/{workspace_id}/shared-reflections", headers=headers_c),
        await client.get(
            f"/v1/workspaces/{workspace_id}/shared-reflections/{shared['id']}", headers=headers_c
        ),
        await client.delete(
            f"/v1/workspaces/{workspace_id}/shared-reflections/{shared['id']}", headers=headers_c
        ),
    ]
    for response in responses:
        assert response.status_code == 404, response.request.url


# ---------------------------------------------------------------------------
# PRIVATE stays private -- no workspace endpoint ever exposes an un-shared
# PrivateReflection to the partner.
# ---------------------------------------------------------------------------


async def test_private_reflection_never_reachable_via_workspace_without_share(
    client, sessionmaker, lukas_payload
) -> None:
    workspace_id = await _connect(client, sessionmaker, "priv-a@example.com", "priv-b@example.com")
    headers_a = await _switch_user(client, "priv-a@example.com")
    person_id = await _create_person(client, headers_a, lukas_payload)
    await _create_private_reflection(client, headers_a, person_id, "Never shared")

    headers_b = await _switch_user(client, "priv-b@example.com")
    list_response = await client.get(
        f"/v1/workspaces/{workspace_id}/shared-reflections", headers=headers_b
    )
    assert list_response.status_code == 200
    assert list_response.json() == []
