"""PR-V2-11 -- Life Tracking CRUD, Custom-Metrik-Definitionen und IDOR-Grenzen
(routes/life_tracking.py). Folgt dem `_login`/`_create_person`-Helfermuster aus
test_private_reflections.py.
"""

from __future__ import annotations

import pytest
from sqlalchemy.exc import IntegrityError

from numra_api.auth.passwords import hash_password
from numra_api.models import LifeTrackingEntry
from numra_api.repositories.users import create_user

pytestmark = pytest.mark.integration


async def _login(client, sessionmaker, email: str = "tracking@example.com") -> dict:
    async with sessionmaker() as db:
        await create_user(db, email=email, password_hash=hash_password("password12345"))
        await db.commit()
    await client.post("/v1/auth/logout")
    response = await client.post(
        "/v1/auth/login", json={"email": email, "password": "password12345"}
    )
    assert response.status_code == 200
    return {"x-csrf-token": client.cookies["numra_csrf"]}


async def _create_person(client, headers, lukas_payload) -> str:
    response = await client.post("/v1/people", json=lukas_payload, headers=headers)
    assert response.status_code == 201
    return response.json()["id"]


async def test_life_tracking_entry_crud_happy_path(client, sessionmaker, lukas_payload) -> None:
    headers = await _login(client, sessionmaker)
    person_id = await _create_person(client, headers, lukas_payload)

    create_response = await client.post(
        f"/v1/people/{person_id}/life-tracking-entries",
        json={"entry_date": "2026-08-19", "mood": 7, "energy": 4, "note": "Ruhiger Tag."},
        headers=headers,
    )
    assert create_response.status_code == 201
    entry = create_response.json()
    assert entry["person_id"] == person_id
    assert entry["mood"] == 7
    assert entry["sleep"] is None
    assert entry["custom_metrics"] == {}

    list_response = await client.get(
        f"/v1/people/{person_id}/life-tracking-entries", headers=headers
    )
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1

    get_response = await client.get(f"/v1/life-tracking-entries/{entry['id']}", headers=headers)
    assert get_response.status_code == 200

    patch_response = await client.patch(
        f"/v1/life-tracking-entries/{entry['id']}", json={"energy": 9}, headers=headers
    )
    assert patch_response.status_code == 200
    assert patch_response.json()["energy"] == 9
    assert patch_response.json()["mood"] == 7  # nicht gesendetes Feld bleibt unangetastet

    delete_response = await client.delete(
        f"/v1/life-tracking-entries/{entry['id']}", headers=headers
    )
    assert delete_response.status_code == 204
    assert (
        await client.get(f"/v1/life-tracking-entries/{entry['id']}", headers=headers)
    ).status_code == 404


async def test_metric_value_outside_scale_is_rejected(client, sessionmaker, lukas_payload) -> None:
    headers = await _login(client, sessionmaker, email="tracking-scale@example.com")
    person_id = await _create_person(client, headers, lukas_payload)

    response = await client.post(
        f"/v1/people/{person_id}/life-tracking-entries",
        json={"entry_date": "2026-08-19", "mood": 11},
        headers=headers,
    )
    assert response.status_code == 422


async def test_second_entry_for_same_date_conflicts(client, sessionmaker, lukas_payload) -> None:
    """`uq_life_tracking_entries_person_date` -- ein Tag, ein Eintrag."""
    headers = await _login(client, sessionmaker, email="tracking-dup@example.com")
    person_id = await _create_person(client, headers, lukas_payload)

    first = await client.post(
        f"/v1/people/{person_id}/life-tracking-entries",
        json={"entry_date": "2026-08-19", "mood": 5},
        headers=headers,
    )
    assert first.status_code == 201

    with pytest.raises(IntegrityError):  # schlaegt bis zum Commit durch
        await client.post(
            f"/v1/people/{person_id}/life-tracking-entries",
            json={"entry_date": "2026-08-19", "mood": 6},
            headers=headers,
        )


async def test_custom_metric_definition_and_values(client, sessionmaker, lukas_payload) -> None:
    headers = await _login(client, sessionmaker, email="tracking-custom@example.com")
    person_id = await _create_person(client, headers, lukas_payload)

    definition = (
        await client.post(
            f"/v1/people/{person_id}/custom-metric-definitions",
            json={"metric_key": "caffeine", "label": "Koffein", "scale_min": 1, "scale_max": 5},
            headers=headers,
        )
    ).json()
    assert definition["metric_key"] == "caffeine"
    assert definition["active"] is True

    entry = await client.post(
        f"/v1/people/{person_id}/life-tracking-entries",
        json={"entry_date": "2026-08-19", "mood": 6, "custom_metrics": {"caffeine": 3}},
        headers=headers,
    )
    assert entry.status_code == 201
    assert entry.json()["custom_metrics"] == {"caffeine": 3}

    out_of_scale = await client.post(
        f"/v1/people/{person_id}/life-tracking-entries",
        json={"entry_date": "2026-08-20", "custom_metrics": {"caffeine": 9}},
        headers=headers,
    )
    assert out_of_scale.status_code == 422
    assert out_of_scale.json()["code"] == "METRIC_VALUE_OUT_OF_SCALE"

    unknown = await client.post(
        f"/v1/people/{person_id}/life-tracking-entries",
        json={"entry_date": "2026-08-21", "custom_metrics": {"nicht_definiert": 3}},
        headers=headers,
    )
    assert unknown.status_code == 404


async def test_metric_key_is_immutable(client, sessionmaker, lukas_payload) -> None:
    headers = await _login(client, sessionmaker, email="tracking-immutable@example.com")
    person_id = await _create_person(client, headers, lukas_payload)

    await client.post(
        f"/v1/people/{person_id}/custom-metric-definitions",
        json={"metric_key": "caffeine", "label": "Koffein"},
        headers=headers,
    )
    duplicate = await client.post(
        f"/v1/people/{person_id}/custom-metric-definitions",
        json={"metric_key": "caffeine", "label": "Koffein neu gedeutet"},
        headers=headers,
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["code"] == "METRIC_KEY_IMMUTABLE"


async def test_patch_definition_changes_label_and_retires_but_keeps_key(
    client, sessionmaker, lukas_payload
) -> None:
    headers = await _login(client, sessionmaker, email="tracking-retire@example.com")
    person_id = await _create_person(client, headers, lukas_payload)

    definition = (
        await client.post(
            f"/v1/people/{person_id}/custom-metric-definitions",
            json={"metric_key": "caffeine", "label": "Koffein"},
            headers=headers,
        )
    ).json()

    patched = await client.patch(
        f"/v1/custom-metric-definitions/{definition['id']}",
        json={"label": "Koffeinmenge", "active": False},
        headers=headers,
    )
    assert patched.status_code == 200
    body = patched.json()
    assert body["metric_key"] == "caffeine"
    assert body["label"] == "Koffeinmenge"
    assert body["active"] is False
    assert body["retired_at"] is not None

    # Eine stillgelegte Definition nimmt keine neuen Werte mehr an.
    rejected = await client.post(
        f"/v1/people/{person_id}/life-tracking-entries",
        json={"entry_date": "2026-08-22", "custom_metrics": {"caffeine": 2}},
        headers=headers,
    )
    assert rejected.status_code == 404


async def test_standard_metric_key_in_custom_metrics_is_rejected(
    client, sessionmaker, lukas_payload
) -> None:
    headers = await _login(client, sessionmaker, email="tracking-collide@example.com")
    person_id = await _create_person(client, headers, lukas_payload)

    response = await client.post(
        f"/v1/people/{person_id}/life-tracking-entries",
        json={"entry_date": "2026-08-19", "custom_metrics": {"mood": 5}},
        headers=headers,
    )
    assert response.status_code == 422


async def test_entries_isolated_per_user(client, sessionmaker, lukas_payload) -> None:
    headers_a = await _login(client, sessionmaker, email="tracking-iso-a@example.com")
    person_id_a = await _create_person(client, headers_a, lukas_payload)
    entry = (
        await client.post(
            f"/v1/people/{person_id_a}/life-tracking-entries",
            json={"entry_date": "2026-08-19", "mood": 5},
            headers=headers_a,
        )
    ).json()

    headers_b = await _login(client, sessionmaker, email="tracking-iso-b@example.com")

    assert (
        await client.get(f"/v1/life-tracking-entries/{entry['id']}", headers=headers_b)
    ).status_code == 404
    assert (
        await client.patch(
            f"/v1/life-tracking-entries/{entry['id']}", json={"mood": 1}, headers=headers_b
        )
    ).status_code == 404
    assert (
        await client.delete(f"/v1/life-tracking-entries/{entry['id']}", headers=headers_b)
    ).status_code == 404
    assert (
        await client.get(f"/v1/people/{person_id_a}/life-tracking-entries", headers=headers_b)
    ).status_code == 404


async def test_create_entry_without_csrf_rejected(client, sessionmaker, lukas_payload) -> None:
    headers = await _login(client, sessionmaker, email="tracking-csrf@example.com")
    person_id = await _create_person(client, headers, lukas_payload)

    response = await client.post(
        f"/v1/people/{person_id}/life-tracking-entries",
        json={"entry_date": "2026-08-19", "mood": 5},
    )
    assert response.status_code == 403
    assert response.json()["code"] == "CSRF_VALIDATION_FAILED"


def test_life_tracking_entry_has_no_persisted_personal_day_column() -> None:
    """specs/v2/evidence-policy.md: "It never stores a new Personal Day/Month/Year
    value". Ein Schema-Test, kein Verhaltenstest -- die Regel muss strukturell
    gelten, nicht nur an den heute vorhandenen Codepfaden."""
    column_names = set(LifeTrackingEntry.__table__.columns.keys())
    assert not any("personal" in name for name in column_names)
    assert column_names == {
        "id",
        "user_id",
        "person_id",
        "entry_date",
        "calculation_id",
        "mood",
        "energy",
        "sleep",
        "stress",
        "focus",
        "note",
        "created_at",
        "updated_at",
    }
