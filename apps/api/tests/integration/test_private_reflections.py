from __future__ import annotations

import pytest

from numra_api.auth.passwords import hash_password
from numra_api.repositories.users import create_user

pytestmark = pytest.mark.integration


async def _login(client, sessionmaker, email: str = "reflections@example.com") -> dict:
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


async def test_private_reflection_crud_happy_path(client, sessionmaker, lukas_payload) -> None:
    headers = await _login(client, sessionmaker)
    person_id = await _create_person(client, headers, lukas_payload)

    create_response = await client.post(
        f"/v1/people/{person_id}/private-reflections",
        json={"entry_date": "2026-08-19", "content": "Heute war ein guter Tag."},
        headers=headers,
    )
    assert create_response.status_code == 201
    reflection = create_response.json()
    assert reflection["person_id"] == person_id
    assert reflection["content"] == "Heute war ein guter Tag."

    list_response = await client.get(f"/v1/people/{person_id}/private-reflections", headers=headers)
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1

    get_response = await client.get(f"/v1/private-reflections/{reflection['id']}", headers=headers)
    assert get_response.status_code == 200
    assert get_response.json()["id"] == reflection["id"]

    patch_response = await client.patch(
        f"/v1/private-reflections/{reflection['id']}",
        json={"content": "Aktualisierter Eintrag."},
        headers=headers,
    )
    assert patch_response.status_code == 200
    assert patch_response.json()["content"] == "Aktualisierter Eintrag."
    assert patch_response.json()["entry_date"] == "2026-08-19"  # unset field untouched

    delete_response = await client.delete(
        f"/v1/private-reflections/{reflection['id']}", headers=headers
    )
    assert delete_response.status_code == 204

    get_after_delete = await client.get(
        f"/v1/private-reflections/{reflection['id']}", headers=headers
    )
    assert get_after_delete.status_code == 404


async def test_create_private_reflection_without_csrf_rejected(
    client, sessionmaker, lukas_payload
) -> None:
    headers = await _login(client, sessionmaker)
    person_id = await _create_person(client, headers, lukas_payload)

    response = await client.post(
        f"/v1/people/{person_id}/private-reflections",
        json={"entry_date": "2026-08-19", "content": "no csrf"},
    )
    assert response.status_code == 403
    assert response.json()["code"] == "CSRF_VALIDATION_FAILED"


async def test_create_private_reflection_foreign_person_id_not_found(
    client, sessionmaker, lukas_payload
) -> None:
    headers_a = await _login(client, sessionmaker, email="reflections-a@example.com")
    person_id_a = await _create_person(client, headers_a, lukas_payload)

    await client.post("/v1/auth/logout")
    headers_b = await _login(client, sessionmaker, email="reflections-b@example.com")

    response = await client.post(
        f"/v1/people/{person_id_a}/private-reflections",
        json={"entry_date": "2026-08-19", "content": "should not be created"},
        headers=headers_b,
    )
    assert response.status_code == 404


async def test_private_reflections_isolated_per_user(client, sessionmaker, lukas_payload) -> None:
    headers_a = await _login(client, sessionmaker, email="reflections-iso-a@example.com")
    person_id_a = await _create_person(client, headers_a, lukas_payload)
    reflection = (
        await client.post(
            f"/v1/people/{person_id_a}/private-reflections",
            json={"entry_date": "2026-08-19", "content": "private to A"},
            headers=headers_a,
        )
    ).json()

    await client.post("/v1/auth/logout")
    headers_b = await _login(client, sessionmaker, email="reflections-iso-b@example.com")

    get_response = await client.get(
        f"/v1/private-reflections/{reflection['id']}", headers=headers_b
    )
    assert get_response.status_code == 404

    patch_response = await client.patch(
        f"/v1/private-reflections/{reflection['id']}",
        json={"content": "hijacked"},
        headers=headers_b,
    )
    assert patch_response.status_code == 404

    delete_response = await client.delete(
        f"/v1/private-reflections/{reflection['id']}", headers=headers_b
    )
    assert delete_response.status_code == 404

    list_response = await client.get(
        f"/v1/people/{person_id_a}/private-reflections", headers=headers_b
    )
    assert list_response.status_code == 404
