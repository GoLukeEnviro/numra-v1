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


async def test_create_person_rejects_future_birth_date(client, sessionmaker) -> None:
    headers = await _login(client, sessionmaker)
    response = await client.post(
        "/v1/people",
        json={
            "birth_first_names": "Future",
            "birth_last_name": "Person",
            "birth_date": "2999-01-01",
        },
        headers=headers,
    )
    assert response.status_code == 422
    assert response.json()["code"] == "FUTURE_BIRTH_DATE_NOT_ALLOWED"


async def test_create_person_without_csrf_rejected(client, sessionmaker) -> None:
    await _login(client, sessionmaker)
    response = await client.post(
        "/v1/people",
        json={"birth_first_names": "No", "birth_last_name": "Csrf", "birth_date": "1990-01-01"},
    )
    assert response.status_code == 403
    assert response.json()["code"] == "CSRF_VALIDATION_FAILED"


async def test_person_and_golden_calculation_flow(client, sessionmaker, lukas_payload) -> None:
    headers = await _login(client, sessionmaker)

    create_response = await client.post("/v1/people", json=lukas_payload, headers=headers)
    assert create_response.status_code == 201
    person = create_response.json()
    person_id = person["id"]
    assert person["birth_first_names"] == "Lukas"

    list_response = await client.get("/v1/people")
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1

    calc_response = await client.post(
        f"/v1/people/{person_id}/calculations", json={"as_of_date": "2026-08-19"}, headers=headers
    )
    assert calc_response.status_code == 201
    calc = calc_response.json()
    core = calc["canonical_profile"]["core_numbers"]
    assert core["life_path"]["display_value"] == "22/4"
    assert core["expression"]["display_value"] == "62/8"
    assert core["soul_urge"]["display_value"] == "18/9"
    assert core["personality"]["display_value"] == "44/8"
    assert calc["canonical_profile"]["timing"]["personal_year"]["display_value"] == "17/8"

    get_calc_response = await client.get(f"/v1/calculations/{calc['id']}")
    assert get_calc_response.status_code == 200
    assert get_calc_response.json()["deterministic_hash"] == calc["deterministic_hash"]

    timing_response = await client.get(
        f"/v1/people/{person_id}/timing", params={"as_of_date": "2026-08-19"}
    )
    assert timing_response.status_code == 200
    assert timing_response.json()["personal_year"]["display_value"] == "17/8"


async def test_patch_person_updates_current_name(client, sessionmaker, lukas_payload) -> None:
    headers = await _login(client, sessionmaker)
    create_response = await client.post("/v1/people", json=lukas_payload, headers=headers)
    person_id = create_response.json()["id"]

    patch_response = await client.patch(
        f"/v1/people/{person_id}",
        json={"preferred_name": "Luke"},
        headers=headers,
    )
    assert patch_response.status_code == 200
    assert patch_response.json()["preferred_name"] == "Luke"


async def test_patch_person_can_edit_birth_fields(client, sessionmaker, lukas_payload) -> None:
    headers = await _login(client, sessionmaker)
    person_id = (await client.post("/v1/people", json=lukas_payload, headers=headers)).json()["id"]

    patch_response = await client.patch(
        f"/v1/people/{person_id}",
        json={
            "birth_first_names": "Luca",
            "birth_middle_names": None,
            "birth_place": {"display_name": "Düsseldorf", "country_code": "DE"},
        },
        headers=headers,
    )
    assert patch_response.status_code == 200
    updated = patch_response.json()
    assert updated["birth_first_names"] == "Luca"
    assert updated["birth_middle_names"] is None
    assert updated["birth_place"]["display_name"] == "Düsseldorf"
    # birth_last_name/birth_date were not sent -- untouched.
    assert updated["birth_last_name"] == "Springer"
    assert updated["birth_date"] == "1986-07-18"


async def test_patch_person_rejects_future_birth_date(client, sessionmaker, lukas_payload) -> None:
    headers = await _login(client, sessionmaker)
    person_id = (await client.post("/v1/people", json=lukas_payload, headers=headers)).json()["id"]

    response = await client.patch(
        f"/v1/people/{person_id}",
        json={"birth_date": "2999-01-01"},
        headers=headers,
    )
    assert response.status_code == 422
    assert response.json()["code"] == "FUTURE_BIRTH_DATE_NOT_ALLOWED"


async def test_editing_person_never_mutates_existing_calculations(
    client, sessionmaker, lukas_payload
) -> None:
    """V1.5 Epic B's core guarantee: a Calculation is an immutable snapshot. Editing
    the Person it was computed from -- even a canon-sensitive field like the birth
    name -- must never change an already-persisted Calculation's stored hash or
    profile. Only a *new* calculation reflects the edited input."""
    headers = await _login(client, sessionmaker)
    person_id = (await client.post("/v1/people", json=lukas_payload, headers=headers)).json()["id"]

    calc_a = (
        await client.post(
            f"/v1/people/{person_id}/calculations",
            json={"as_of_date": "2026-01-01"},
            headers=headers,
        )
    ).json()
    assert calc_a["canonical_profile"]["core_numbers"]["life_path"]["display_value"] == "22/4"

    # A canon-sensitive edit: the birth name itself, which the Life Path/Expression/
    # Soul Urge/Personality calculations are all derived from.
    patch_response = await client.patch(
        f"/v1/people/{person_id}",
        json={"birth_first_names": "Someone", "birth_last_name": "Else"},
        headers=headers,
    )
    assert patch_response.status_code == 200

    reloaded_calc_a = (await client.get(f"/v1/calculations/{calc_a['id']}")).json()
    assert reloaded_calc_a["deterministic_hash"] == calc_a["deterministic_hash"]
    assert reloaded_calc_a["canonical_profile"] == calc_a["canonical_profile"]

    calc_b = (
        await client.post(
            f"/v1/people/{person_id}/calculations",
            json={"as_of_date": "2026-01-01"},
            headers=headers,
        )
    ).json()
    assert calc_b["deterministic_hash"] != calc_a["deterministic_hash"]

    history = (await client.get(f"/v1/people/{person_id}/calculations")).json()
    assert {c["id"] for c in history} == {calc_a["id"], calc_b["id"]}


async def test_delete_person_cascades_calculations(client, sessionmaker, lukas_payload) -> None:
    headers = await _login(client, sessionmaker)
    create_response = await client.post("/v1/people", json=lukas_payload, headers=headers)
    person_id = create_response.json()["id"]

    calc_response = await client.post(
        f"/v1/people/{person_id}/calculations", json={"as_of_date": "2026-01-01"}, headers=headers
    )
    calc_id = calc_response.json()["id"]

    delete_response = await client.delete(f"/v1/people/{person_id}", headers=headers)
    assert delete_response.status_code == 204

    get_person_response = await client.get(f"/v1/people/{person_id}")
    assert get_person_response.status_code == 404

    get_calc_response = await client.get(f"/v1/calculations/{calc_id}")
    assert get_calc_response.status_code == 404


async def test_person_isolated_per_user(client, sessionmaker, lukas_payload) -> None:
    headers_a = await _login(client, sessionmaker, email="a@example.com")
    create_response = await client.post("/v1/people", json=lukas_payload, headers=headers_a)
    person_id = create_response.json()["id"]

    await client.post("/v1/auth/logout")
    headers_b = await _login(client, sessionmaker, email="b@example.com")

    response = await client.get(f"/v1/people/{person_id}", headers=headers_b)
    assert response.status_code == 404


async def test_list_calculations_for_person_is_server_authoritative(
    client, sessionmaker, lukas_payload
) -> None:
    """The calculation-history list is the server truth a fresh browser context (no
    LocalStorage) relies on to discover existing snapshots -- V1.5 Epic A."""
    headers = await _login(client, sessionmaker)
    person_id = (await client.post("/v1/people", json=lukas_payload, headers=headers)).json()["id"]

    first = (
        await client.post(
            f"/v1/people/{person_id}/calculations",
            json={"as_of_date": "2026-01-01"},
            headers=headers,
        )
    ).json()
    second = (
        await client.post(
            f"/v1/people/{person_id}/calculations",
            json={"as_of_date": "2026-06-01"},
            headers=headers,
        )
    ).json()

    list_response = await client.get(f"/v1/people/{person_id}/calculations")
    assert list_response.status_code == 200
    summaries = list_response.json()
    assert [s["id"] for s in summaries] == [second["id"], first["id"]]  # newest first
    # List cards never need the full canonical profile payload.
    assert "canonical_profile" not in summaries[0]
    assert summaries[0]["deterministic_hash"] == second["deterministic_hash"]
    assert summaries[0]["as_of_date"] == "2026-06-01"


async def test_list_calculations_isolated_per_user_and_unknown_person(
    client, sessionmaker, lukas_payload
) -> None:
    headers_a = await _login(client, sessionmaker, email="calc-list-a@example.com")
    person_id = (await client.post("/v1/people", json=lukas_payload, headers=headers_a)).json()[
        "id"
    ]
    await client.post(
        f"/v1/people/{person_id}/calculations",
        json={"as_of_date": "2026-01-01"},
        headers=headers_a,
    )

    await client.post("/v1/auth/logout")
    headers_b = await _login(client, sessionmaker, email="calc-list-b@example.com")

    response = await client.get(f"/v1/people/{person_id}/calculations", headers=headers_b)
    assert response.status_code == 404


async def test_identity_history_is_recorded_truthfully(client, sessionmaker, lukas_payload) -> None:
    """V1.5 Epic C: creating a person records a birth identity (with valid_from =
    birth_date, a genuinely known fact); editing current/preferred names appends
    new entries with no invented effective date, never rewriting the earlier ones."""
    headers = await _login(client, sessionmaker)
    person_id = (await client.post("/v1/people", json=lukas_payload, headers=headers)).json()["id"]

    after_create = (await client.get(f"/v1/people/{person_id}/identities")).json()
    assert len(after_create) == 1
    birth_entry = after_create[0]
    assert birth_entry["kind"] == "birth"
    assert birth_entry["first_names"] == "Lukas"
    assert birth_entry["last_name"] == "Springer"
    assert birth_entry["valid_from"] == "1986-07-18"  # a known fact, not a guess
    assert birth_entry["recorded_at"] is not None

    await client.patch(
        f"/v1/people/{person_id}",
        json={"preferred_name": "Luke"},
        headers=headers,
    )
    after_preferred = (await client.get(f"/v1/people/{person_id}/identities")).json()
    assert len(after_preferred) == 2
    preferred_entry = next(e for e in after_preferred if e["kind"] == "preferred")
    assert preferred_entry["first_names"] == "Luke"
    assert preferred_entry["valid_from"] is None  # never invented

    # Re-saving the identical preferred_name must not append a duplicate row.
    await client.patch(
        f"/v1/people/{person_id}",
        json={"preferred_name": "Luke"},
        headers=headers,
    )
    unchanged = (await client.get(f"/v1/people/{person_id}/identities")).json()
    assert len(unchanged) == 2

    # A genuine change appends a new row -- the old one is never rewritten.
    await client.patch(
        f"/v1/people/{person_id}",
        json={"preferred_name": "L."},
        headers=headers,
    )
    after_second_change = (await client.get(f"/v1/people/{person_id}/identities")).json()
    assert len(after_second_change) == 3
    preferred_names = sorted(
        e["first_names"] for e in after_second_change if e["kind"] == "preferred"
    )
    assert preferred_names == ["L.", "Luke"]


async def test_identity_history_isolated_per_user(client, sessionmaker, lukas_payload) -> None:
    headers_a = await _login(client, sessionmaker, email="identity-a@example.com")
    person_id = (await client.post("/v1/people", json=lukas_payload, headers=headers_a)).json()[
        "id"
    ]

    await client.post("/v1/auth/logout")
    headers_b = await _login(client, sessionmaker, email="identity-b@example.com")

    response = await client.get(f"/v1/people/{person_id}/identities", headers=headers_b)
    assert response.status_code == 404
