from __future__ import annotations

import pytest

from numra_api.auth.passwords import hash_password
from numra_api.repositories.users import create_user

pytestmark = pytest.mark.integration


async def _login(client, sessionmaker, email: str = "notes@example.com") -> dict:
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


async def test_private_note_crud_happy_path(client, sessionmaker, lukas_payload) -> None:
    headers = await _login(client, sessionmaker)
    person_id = await _create_person(client, headers, lukas_payload)

    create_response = await client.post(
        f"/v1/people/{person_id}/private-notes",
        json={"title": "Idee", "content": "Eine Notiz."},
        headers=headers,
    )
    assert create_response.status_code == 201
    note = create_response.json()
    assert note["person_id"] == person_id
    assert note["title"] == "Idee"

    list_response = await client.get(f"/v1/people/{person_id}/private-notes", headers=headers)
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1

    get_response = await client.get(f"/v1/private-notes/{note['id']}", headers=headers)
    assert get_response.status_code == 200
    assert get_response.json()["id"] == note["id"]

    patch_response = await client.patch(
        f"/v1/private-notes/{note['id']}",
        json={"title": None},
        headers=headers,
    )
    assert patch_response.status_code == 200
    assert patch_response.json()["title"] is None
    assert patch_response.json()["content"] == "Eine Notiz."  # unset field untouched

    delete_response = await client.delete(f"/v1/private-notes/{note['id']}", headers=headers)
    assert delete_response.status_code == 204

    get_after_delete = await client.get(f"/v1/private-notes/{note['id']}", headers=headers)
    assert get_after_delete.status_code == 404


async def test_create_private_note_without_csrf_rejected(
    client, sessionmaker, lukas_payload
) -> None:
    headers = await _login(client, sessionmaker)
    person_id = await _create_person(client, headers, lukas_payload)

    response = await client.post(
        f"/v1/people/{person_id}/private-notes",
        json={"content": "no csrf"},
    )
    assert response.status_code == 403
    assert response.json()["code"] == "CSRF_VALIDATION_FAILED"


async def test_create_private_note_foreign_person_id_not_found(
    client, sessionmaker, lukas_payload
) -> None:
    headers_a = await _login(client, sessionmaker, email="notes-a@example.com")
    person_id_a = await _create_person(client, headers_a, lukas_payload)

    await client.post("/v1/auth/logout")
    headers_b = await _login(client, sessionmaker, email="notes-b@example.com")

    response = await client.post(
        f"/v1/people/{person_id_a}/private-notes",
        json={"content": "should not be created"},
        headers=headers_b,
    )
    assert response.status_code == 404


async def test_private_notes_isolated_per_user(client, sessionmaker, lukas_payload) -> None:
    headers_a = await _login(client, sessionmaker, email="notes-iso-a@example.com")
    person_id_a = await _create_person(client, headers_a, lukas_payload)
    note = (
        await client.post(
            f"/v1/people/{person_id_a}/private-notes",
            json={"content": "private to A"},
            headers=headers_a,
        )
    ).json()

    await client.post("/v1/auth/logout")
    headers_b = await _login(client, sessionmaker, email="notes-iso-b@example.com")

    get_response = await client.get(f"/v1/private-notes/{note['id']}", headers=headers_b)
    assert get_response.status_code == 404

    patch_response = await client.patch(
        f"/v1/private-notes/{note['id']}",
        json={"content": "hijacked"},
        headers=headers_b,
    )
    assert patch_response.status_code == 404

    delete_response = await client.delete(f"/v1/private-notes/{note['id']}", headers=headers_b)
    assert delete_response.status_code == 404

    list_response = await client.get(f"/v1/people/{person_id_a}/private-notes", headers=headers_b)
    assert list_response.status_code == 404
