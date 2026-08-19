from __future__ import annotations

import pytest

from numra_api.auth.passwords import hash_password
from numra_api.repositories.users import create_user

pytestmark = pytest.mark.integration


async def _login(client, sessionmaker, email: str = "rel@example.com") -> dict:
    async with sessionmaker() as db:
        await create_user(db, email=email, password_hash=hash_password("password12345"))
        await db.commit()
    response = await client.post(
        "/v1/auth/login", json={"email": email, "password": "password12345"}
    )
    assert response.status_code == 200
    return {"x-csrf-token": client.cookies["numra_csrf"]}


async def test_relationship_comparison_no_percentage(client, sessionmaker, lukas_payload) -> None:
    headers = await _login(client, sessionmaker)

    person_a = (await client.post("/v1/people", json=lukas_payload, headers=headers)).json()
    other_payload = {**lukas_payload, "birth_first_names": "Anna", "birth_last_name": "Beispiel"}
    person_b = (await client.post("/v1/people", json=other_payload, headers=headers)).json()

    calc_a = (
        await client.post(
            f"/v1/people/{person_a['id']}/calculations",
            json={"as_of_date": "2026-01-01"},
            headers=headers,
        )
    ).json()
    calc_b = (
        await client.post(
            f"/v1/people/{person_b['id']}/calculations",
            json={"as_of_date": "2026-01-01"},
            headers=headers,
        )
    ).json()

    response = await client.post(
        "/v1/relationships",
        json={"calculation_a_id": calc_a["id"], "calculation_b_id": calc_b["id"]},
        headers=headers,
    )
    assert response.status_code == 201
    comparison = response.json()["comparison"]

    assert set(comparison.keys()) == {
        "life_path",
        "expression",
        "soul_urge",
        "personality",
        "maturity",
        "personal_year",
        "personal_month",
        "personal_day",
    }
    for metric in comparison.values():
        assert set(metric.keys()) == {"person_a", "person_b", "match"}

    get_response = await client.get(f"/v1/relationships/{response.json()['id']}")
    assert get_response.status_code == 200
