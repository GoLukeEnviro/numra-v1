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
    detail = get_response.json()
    assert detail["person_a"]["display_name"] == "Lukas Springer"
    assert detail["person_b"]["display_name"] == "Anna Beispiel"


async def test_relationship_insights_have_no_score_and_cite_knowledge(
    client, sessionmaker, lukas_payload
) -> None:
    """V1.5 Epic F: relationship intelligence is structured and knowledge-sourced --
    never a compatibility percentage or any other invented numeric match score
    (canon-spec.md §33, RESERVED_UNFROZEN)."""
    headers = await _login(client, sessionmaker, email="insights@example.com")

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
    body = response.json()
    insights = body["insights"]

    assert {i["metric_id"] for i in insights} == {
        "life_path",
        "expression",
        "soul_urge",
        "personality",
    }
    for insight in insights:
        assert set(insight.keys()) == {
            "metric_id",
            "person_a_number",
            "person_b_number",
            "shared_number",
            "person_a_relationship_themes",
            "person_b_relationship_themes",
            "knowledge_refs",
        }
        # Hard failure condition: no compatibility percentage/match score anywhere.
        assert "score" not in insight
        assert "percentage" not in insight
        assert "match" not in insight
        assert len(insight["person_a_relationship_themes"]) > 0
        assert len(insight["person_b_relationship_themes"]) > 0
        assert insight["shared_number"] == (
            insight["person_a_number"] == insight["person_b_number"]
        )
        for ref in insight["knowledge_refs"]:
            assert ref.startswith("numbers/")

    get_response = await client.get(f"/v1/relationships/{body['id']}")
    assert get_response.status_code == 200
    assert get_response.json()["insights"] == insights


async def test_list_relationships_resolves_person_names(
    client, sessionmaker, lukas_payload
) -> None:
    """The relationship library (V1.5 Epic A/E) is server-authoritative and resolves
    real names -- a list card must never fall back to "Person A"/"Person B", and a
    fresh browser context with no LocalStorage must still see it."""
    headers = await _login(client, sessionmaker, email="list-rel@example.com")

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

    create_response = await client.post(
        "/v1/relationships",
        json={"calculation_a_id": calc_a["id"], "calculation_b_id": calc_b["id"]},
        headers=headers,
    )
    relationship_id = create_response.json()["id"]

    list_response = await client.get("/v1/relationships")
    assert list_response.status_code == 200
    [summary] = list_response.json()
    assert summary["id"] == relationship_id
    assert summary["person_a"]["display_name"] == "Lukas Springer"
    assert summary["person_a"]["id"] == person_a["id"]
    assert summary["person_b"]["display_name"] == "Anna Beispiel"
    assert "comparison" not in summary  # list cards don't need the full comparison


async def test_list_relationships_isolated_per_user(client, sessionmaker, lukas_payload) -> None:
    headers_a = await _login(client, sessionmaker, email="list-rel-a@example.com")
    person_a = (await client.post("/v1/people", json=lukas_payload, headers=headers_a)).json()
    person_b = (
        await client.post(
            "/v1/people",
            json={**lukas_payload, "birth_first_names": "Second"},
            headers=headers_a,
        )
    ).json()
    calc_a = (
        await client.post(
            f"/v1/people/{person_a['id']}/calculations",
            json={"as_of_date": "2026-01-01"},
            headers=headers_a,
        )
    ).json()
    calc_b = (
        await client.post(
            f"/v1/people/{person_b['id']}/calculations",
            json={"as_of_date": "2026-01-01"},
            headers=headers_a,
        )
    ).json()
    await client.post(
        "/v1/relationships",
        json={"calculation_a_id": calc_a["id"], "calculation_b_id": calc_b["id"]},
        headers=headers_a,
    )

    await client.post("/v1/auth/logout")
    headers_b = await _login(client, sessionmaker, email="list-rel-b@example.com")

    response = await client.get("/v1/relationships", headers=headers_b)
    assert response.status_code == 200
    assert response.json() == []


async def test_create_relationship_by_person_resolves_latest_calculation(
    client, sessionmaker, lukas_payload
) -> None:
    """V1.5 Epic E: the product-facing path -- select two people, not two pasted
    calculation UUIDs. The route resolves each person's latest calculation itself."""
    headers = await _login(client, sessionmaker, email="rel-by-person@example.com")

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
    await client.post(
        f"/v1/people/{person_b['id']}/calculations",
        json={"as_of_date": "2026-01-01"},
        headers=headers,
    )
    # A second, later calculation for A -- the route must resolve to THIS one, not
    # the first.
    calc_a2 = (
        await client.post(
            f"/v1/people/{person_a['id']}/calculations",
            json={"as_of_date": "2026-02-01"},
            headers=headers,
        )
    ).json()

    response = await client.post(
        "/v1/relationships",
        json={"person_a_id": person_a["id"], "person_b_id": person_b["id"]},
        headers=headers,
    )
    assert response.status_code == 201
    body = response.json()
    assert body["calculation_a_id"] == calc_a2["id"]
    assert body["calculation_a_id"] != calc_a["id"]
    assert body["person_a"]["display_name"] == "Lukas Springer"
    assert body["person_b"]["display_name"] == "Anna Beispiel"


async def test_create_relationship_by_person_without_calculation_fails_clearly(
    client, sessionmaker, lukas_payload
) -> None:
    headers = await _login(client, sessionmaker, email="rel-no-calc@example.com")
    person_a = (await client.post("/v1/people", json=lukas_payload, headers=headers)).json()
    other_payload = {**lukas_payload, "birth_first_names": "Anna", "birth_last_name": "Beispiel"}
    person_b = (await client.post("/v1/people", json=other_payload, headers=headers)).json()
    # Neither person has a calculation yet.

    response = await client.post(
        "/v1/relationships",
        json={"person_a_id": person_a["id"], "person_b_id": person_b["id"]},
        headers=headers,
    )
    assert response.status_code == 404


async def test_create_relationship_rejects_mixed_or_missing_selectors(
    client, sessionmaker, lukas_payload
) -> None:
    headers = await _login(client, sessionmaker, email="rel-bad-request@example.com")
    person_a = (await client.post("/v1/people", json=lukas_payload, headers=headers)).json()

    neither = await client.post("/v1/relationships", json={}, headers=headers)
    assert neither.status_code == 422

    mixed = await client.post(
        "/v1/relationships",
        json={
            "person_a_id": person_a["id"],
            "person_b_id": person_a["id"],
            "calculation_a_id": str(person_a["id"]),
            "calculation_b_id": str(person_a["id"]),
        },
        headers=headers,
    )
    assert mixed.status_code == 422
