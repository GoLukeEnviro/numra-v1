from __future__ import annotations

import pytest

from numra_api.auth.passwords import hash_password
from numra_api.repositories.users import create_user

pytestmark = pytest.mark.integration


async def _login(client, sessionmaker, email: str = "user@example.com") -> dict:
    async with sessionmaker() as db:
        await create_user(db, email=email, password_hash=hash_password("password12345"))
        await db.commit()
    response = await client.post(
        "/v1/auth/login", json={"email": email, "password": "password12345"}
    )
    assert response.status_code == 200
    return {"x-csrf-token": client.cookies["numra_csrf"]}


@pytest.mark.parametrize(
    ("first_names", "last_name"),
    [
        ("Nachtlauf", "Volltest 20260920T234236Z"),
        ("Müller", "Test2"),
        ("O'Brien", "Name3"),
    ],
)
async def test_calculation_with_digits_or_symbols_in_name_is_a_domain_error(
    client, sessionmaker, first_names: str, last_name: str
) -> None:
    """A name the normalisation pipeline cannot map is a user-input condition, not a
    server fault (#176): the API answers 4xx with the engine's own code instead of
    letting `NormalizationUnsupportedScript` escape as an HTTP 500."""
    headers = await _login(client, sessionmaker)
    create_response = await client.post(
        "/v1/people",
        json={
            "birth_first_names": first_names,
            "birth_last_name": last_name,
            "birth_date": "1988-11-02",
        },
        headers=headers,
    )
    assert create_response.status_code == 201, create_response.text
    person_id = create_response.json()["id"]

    response = await client.post(
        f"/v1/people/{person_id}/calculations",
        json={"as_of_date": "2026-09-21"},
        headers=headers,
    )

    assert response.status_code == 422, response.text
    body = response.json()
    assert body["code"] == "NORMALIZATION_UNSUPPORTED_SCRIPT"
    # The message names the offending characters so a client can act on it, and it
    # never becomes a 5xx that monitors would read as an outage.
    assert "unsupported characters" in body["message"]


async def test_timing_route_with_digits_in_name_is_a_domain_error(client, sessionmaker) -> None:
    """Same mapping on the second engine entry point of this router (`/timing`), which
    recomputes the profile directly instead of going through the persist service."""
    headers = await _login(client, sessionmaker)
    create_response = await client.post(
        "/v1/people",
        json={
            "birth_first_names": "Nachtlauf",
            "birth_last_name": "Volltest 20260921T000000Z",
            "birth_date": "1988-11-02",
        },
        headers=headers,
    )
    assert create_response.status_code == 201, create_response.text
    person_id = create_response.json()["id"]

    response = await client.get(
        f"/v1/people/{person_id}/timing",
        params={"as_of_date": "2026-09-21"},
    )

    assert response.status_code == 422, response.text
    assert response.json()["code"] == "NORMALIZATION_UNSUPPORTED_SCRIPT"
