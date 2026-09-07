from __future__ import annotations

import pytest

from numra_api.auth.passwords import hash_password
from numra_api.repositories.users import create_user

pytestmark = pytest.mark.integration


async def _login(client, sessionmaker, email: str = "workspace@example.com") -> dict:
    async with sessionmaker() as db:
        await create_user(db, email=email, password_hash=hash_password("password12345"))
        await db.commit()
    response = await client.post(
        "/v1/auth/login", json={"email": email, "password": "password12345"}
    )
    assert response.status_code == 200
    return {"x-csrf-token": client.cookies["numra_csrf"]}


async def _create_person(client, headers, lukas_payload) -> str:
    response = await client.post("/v1/people", json=lukas_payload, headers=headers)
    assert response.status_code == 201
    return response.json()["id"]


async def test_workspace_overview_counts_and_latest(client, sessionmaker, lukas_payload) -> None:
    headers = await _login(client, sessionmaker)
    person_id = await _create_person(client, headers, lukas_payload)

    # No calculation yet -- overview must still respond, not 404/500.
    empty_overview = await client.get(
        "/v1/me/workspace", params={"person_id": person_id}, headers=headers
    )
    assert empty_overview.status_code == 200
    body = empty_overview.json()
    assert body["person"]["id"] == person_id
    assert body["latest_calculation"] is None
    assert body["reports"] == {"total": 0, "latest": None}
    assert body["private_reflections"] == {"total": 0, "latest": None}
    assert body["private_notes"] == {"total": 0}
    assert body["personal_tasks"] == {"total": 0, "active": 0}

    older_calc = (
        await client.post(
            f"/v1/people/{person_id}/calculations",
            json={"as_of_date": "2026-01-01"},
            headers=headers,
        )
    ).json()
    newer_calc = (
        await client.post(
            f"/v1/people/{person_id}/calculations",
            json={"as_of_date": "2026-06-01"},
            headers=headers,
        )
    ).json()

    await client.post(
        f"/v1/people/{person_id}/private-reflections",
        json={"entry_date": "2026-08-01", "content": "erste"},
        headers=headers,
    )
    latest_reflection = (
        await client.post(
            f"/v1/people/{person_id}/private-reflections",
            json={"entry_date": "2026-08-19", "content": "neueste"},
            headers=headers,
        )
    ).json()

    await client.post(
        f"/v1/people/{person_id}/private-notes",
        json={"content": "note 1"},
        headers=headers,
    )
    await client.post(
        f"/v1/people/{person_id}/private-notes",
        json={"content": "note 2"},
        headers=headers,
    )

    active_task = (
        await client.post(
            f"/v1/people/{person_id}/personal-tasks",
            json={"title": "aktiv"},
            headers=headers,
        )
    ).json()
    completed_task = (
        await client.post(
            f"/v1/people/{person_id}/personal-tasks",
            json={"title": "wird erledigt"},
            headers=headers,
        )
    ).json()
    await client.patch(
        f"/v1/personal-tasks/{completed_task['id']}",
        json={"status": "COMPLETED"},
        headers=headers,
    )

    overview = await client.get(
        "/v1/me/workspace", params={"person_id": person_id}, headers=headers
    )
    assert overview.status_code == 200
    body = overview.json()
    assert body["latest_calculation"]["id"] == newer_calc["id"]
    assert body["latest_calculation"]["id"] != older_calc["id"]
    assert body["private_reflections"]["total"] == 2
    assert body["private_reflections"]["latest"]["id"] == latest_reflection["id"]
    assert body["private_notes"]["total"] == 2
    assert body["personal_tasks"]["total"] == 2
    assert body["personal_tasks"]["active"] == 1
    assert active_task["id"]  # sanity: fixture used


async def test_workspace_overview_foreign_person_id_not_found(
    client, sessionmaker, lukas_payload
) -> None:
    headers_a = await _login(client, sessionmaker, email="workspace-a@example.com")
    person_id_a = await _create_person(client, headers_a, lukas_payload)

    await client.post("/v1/auth/logout")
    headers_b = await _login(client, sessionmaker, email="workspace-b@example.com")

    response = await client.get(
        "/v1/me/workspace", params={"person_id": person_id_a}, headers=headers_b
    )
    assert response.status_code == 404


async def test_workspace_overview_missing_person_id_is_422(client, sessionmaker) -> None:
    headers = await _login(client, sessionmaker, email="workspace-missing@example.com")

    response = await client.get("/v1/me/workspace", headers=headers)
    assert response.status_code == 422
