from __future__ import annotations

import pytest

from numra_api.auth.passwords import hash_password
from numra_api.repositories.users import create_user

pytestmark = pytest.mark.integration


async def _login(client, sessionmaker, email: str = "tasks@example.com") -> dict:
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


async def test_personal_task_crud_happy_path(client, sessionmaker, lukas_payload) -> None:
    headers = await _login(client, sessionmaker)
    person_id = await _create_person(client, headers, lukas_payload)

    create_response = await client.post(
        f"/v1/people/{person_id}/personal-tasks",
        json={"title": "Meditation", "description": "10 Minuten", "due_date": "2026-09-10"},
        headers=headers,
    )
    assert create_response.status_code == 201
    task = create_response.json()
    assert task["person_id"] == person_id
    assert task["status"] == "ACTIVE"
    assert task["completed_at"] is None

    list_response = await client.get(f"/v1/people/{person_id}/personal-tasks", headers=headers)
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1

    get_response = await client.get(f"/v1/personal-tasks/{task['id']}", headers=headers)
    assert get_response.status_code == 200

    patch_response = await client.patch(
        f"/v1/personal-tasks/{task['id']}",
        json={"description": "15 Minuten"},
        headers=headers,
    )
    assert patch_response.status_code == 200
    assert patch_response.json()["description"] == "15 Minuten"
    assert patch_response.json()["title"] == "Meditation"  # unset field untouched

    delete_response = await client.delete(f"/v1/personal-tasks/{task['id']}", headers=headers)
    assert delete_response.status_code == 204

    get_after_delete = await client.get(f"/v1/personal-tasks/{task['id']}", headers=headers)
    assert get_after_delete.status_code == 404


async def test_personal_task_status_filter(client, sessionmaker, lukas_payload) -> None:
    headers = await _login(client, sessionmaker, email="tasks-filter@example.com")
    person_id = await _create_person(client, headers, lukas_payload)

    active = (
        await client.post(
            f"/v1/people/{person_id}/personal-tasks",
            json={"title": "Aktiv"},
            headers=headers,
        )
    ).json()
    to_archive = (
        await client.post(
            f"/v1/people/{person_id}/personal-tasks",
            json={"title": "Wird archiviert"},
            headers=headers,
        )
    ).json()
    await client.patch(
        f"/v1/personal-tasks/{to_archive['id']}",
        json={"status": "ARCHIVED"},
        headers=headers,
    )

    active_only = await client.get(
        f"/v1/people/{person_id}/personal-tasks",
        params={"status": "ACTIVE"},
        headers=headers,
    )
    assert active_only.status_code == 200
    assert [t["id"] for t in active_only.json()] == [active["id"]]


async def test_personal_task_completed_sets_completed_at_and_archived_reachable_from_any_state(
    client, sessionmaker, lukas_payload
) -> None:
    headers = await _login(client, sessionmaker, email="tasks-transitions@example.com")
    person_id = await _create_person(client, headers, lukas_payload)

    task = (
        await client.post(
            f"/v1/people/{person_id}/personal-tasks",
            json={"title": "Übung"},
            headers=headers,
        )
    ).json()
    assert task["status"] == "ACTIVE"
    assert task["completed_at"] is None

    completed = (
        await client.patch(
            f"/v1/personal-tasks/{task['id']}",
            json={"status": "COMPLETED"},
            headers=headers,
        )
    ).json()
    assert completed["status"] == "COMPLETED"
    assert completed["completed_at"] is not None

    # ARCHIVED reachable directly from ACTIVE.
    task_b = (
        await client.post(
            f"/v1/people/{person_id}/personal-tasks",
            json={"title": "Andere Übung"},
            headers=headers,
        )
    ).json()
    archived_from_active = (
        await client.patch(
            f"/v1/personal-tasks/{task_b['id']}",
            json={"status": "ARCHIVED"},
            headers=headers,
        )
    ).json()
    assert archived_from_active["status"] == "ARCHIVED"
    assert archived_from_active["completed_at"] is None

    # ARCHIVED reachable from COMPLETED too, clearing completed_at.
    archived_from_completed = (
        await client.patch(
            f"/v1/personal-tasks/{task['id']}",
            json={"status": "ARCHIVED"},
            headers=headers,
        )
    ).json()
    assert archived_from_completed["status"] == "ARCHIVED"
    assert archived_from_completed["completed_at"] is None


async def test_create_personal_task_without_csrf_rejected(
    client, sessionmaker, lukas_payload
) -> None:
    headers = await _login(client, sessionmaker)
    person_id = await _create_person(client, headers, lukas_payload)

    response = await client.post(
        f"/v1/people/{person_id}/personal-tasks",
        json={"title": "no csrf"},
    )
    assert response.status_code == 403
    assert response.json()["code"] == "CSRF_VALIDATION_FAILED"


async def test_create_personal_task_foreign_person_id_not_found(
    client, sessionmaker, lukas_payload
) -> None:
    headers_a = await _login(client, sessionmaker, email="tasks-a@example.com")
    person_id_a = await _create_person(client, headers_a, lukas_payload)

    await client.post("/v1/auth/logout")
    headers_b = await _login(client, sessionmaker, email="tasks-b@example.com")

    response = await client.post(
        f"/v1/people/{person_id_a}/personal-tasks",
        json={"title": "should not be created"},
        headers=headers_b,
    )
    assert response.status_code == 404


async def test_personal_tasks_isolated_per_user(client, sessionmaker, lukas_payload) -> None:
    headers_a = await _login(client, sessionmaker, email="tasks-iso-a@example.com")
    person_id_a = await _create_person(client, headers_a, lukas_payload)
    task = (
        await client.post(
            f"/v1/people/{person_id_a}/personal-tasks",
            json={"title": "private to A"},
            headers=headers_a,
        )
    ).json()

    await client.post("/v1/auth/logout")
    headers_b = await _login(client, sessionmaker, email="tasks-iso-b@example.com")

    get_response = await client.get(f"/v1/personal-tasks/{task['id']}", headers=headers_b)
    assert get_response.status_code == 404

    patch_response = await client.patch(
        f"/v1/personal-tasks/{task['id']}",
        json={"status": "COMPLETED"},
        headers=headers_b,
    )
    assert patch_response.status_code == 404

    delete_response = await client.delete(f"/v1/personal-tasks/{task['id']}", headers=headers_b)
    assert delete_response.status_code == 404

    list_response = await client.get(f"/v1/people/{person_id_a}/personal-tasks", headers=headers_b)
    assert list_response.status_code == 404
