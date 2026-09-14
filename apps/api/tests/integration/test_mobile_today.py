from __future__ import annotations

import uuid

import pytest

from numra_api.auth.passwords import hash_password
from numra_api.repositories.users import create_user

pytestmark = pytest.mark.integration

PASSWORD = "correct horse battery staple"


async def _seed_user(sessionmaker, email: str) -> None:
    async with sessionmaker() as db:
        await create_user(db, email=email, password_hash=hash_password(PASSWORD))
        await db.commit()


async def _cookie_login(client, email: str) -> dict[str, str]:
    response = await client.post("/v1/auth/login", json={"email": email, "password": PASSWORD})
    assert response.status_code == 200
    return {"x-csrf-token": client.cookies["numra_csrf"]}


async def _seed_person(client, sessionmaker, email: str, payload: dict) -> dict:
    """Create the person over the browser path (the only one that may write), then drop
    the ambient cookies so the bearer assertions cannot accidentally ride on them."""
    await _seed_user(sessionmaker, email)
    csrf = await _cookie_login(client, email)
    created = await client.post("/v1/people", json=payload, headers=csrf)
    assert created.status_code == 201
    client.cookies.clear()
    return created.json()


async def _bearer_headers(client, email: str) -> dict[str, str]:
    response = await client.post(
        "/v1/auth/mobile/login", json={"email": email, "password": PASSWORD}
    )
    assert response.status_code == 200
    client.cookies.clear()
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


async def test_bearer_token_reads_person_timing_and_daily_brief(
    client, sessionmaker, lukas_payload
) -> None:
    """The native client must reach the already-deterministic read endpoints with its
    opaque token alone -- no cookie, no CSRF, no second computation path."""
    person = await _seed_person(client, sessionmaker, "today@example.com", lukas_payload)
    headers = await _bearer_headers(client, "today@example.com")

    people = await client.get("/v1/people", headers=headers)
    assert people.status_code == 200
    assert [p["id"] for p in people.json()] == [person["id"]]

    timing = await client.get(
        f"/v1/people/{person['id']}/timing",
        params={"as_of_date": "2026-08-19"},
        headers=headers,
    )
    assert timing.status_code == 200
    assert timing.json()["personal_year"]["display_value"] == "17/8"

    brief = await client.get(
        f"/v1/people/{person['id']}/daily-brief",
        params={"as_of_date": "2026-08-19"},
        headers=headers,
    )
    assert brief.status_code == 200
    body = brief.json()
    assert body["person_id"] == person["id"]
    assert [s["metric_id"] for s in body["sections"]] == [
        "personal_year",
        "personal_month",
        "personal_day",
    ]


async def test_cookie_session_still_reads_the_same_endpoints(
    client, sessionmaker, lukas_payload
) -> None:
    """Regression guard: widening the dependency must not cost the browser its
    existing ambient access to the very same routes."""
    await _seed_user(sessionmaker, "cookie-today@example.com")
    csrf = await _cookie_login(client, "cookie-today@example.com")
    person = (await client.post("/v1/people", json=lukas_payload, headers=csrf)).json()

    assert (await client.get("/v1/people")).status_code == 200
    assert (
        await client.get(f"/v1/people/{person['id']}/timing", params={"as_of_date": "2026-08-19"})
    ).status_code == 200
    assert (
        await client.get(
            f"/v1/people/{person['id']}/daily-brief", params={"as_of_date": "2026-08-19"}
        )
    ).status_code == 200


@pytest.mark.parametrize(
    "authorization", [None, "Basic abc", "Bearer", "Bearer ", "Bearer invalid-token"]
)
async def test_missing_and_malformed_bearer_tokens_keep_the_generic_401(
    client, sessionmaker, lukas_payload, authorization
) -> None:
    person = await _seed_person(client, sessionmaker, "reject@example.com", lukas_payload)
    headers = {} if authorization is None else {"Authorization": authorization}

    for path, params in (
        ("/v1/people", None),
        (f"/v1/people/{person['id']}/timing", {"as_of_date": "2026-08-19"}),
        (f"/v1/people/{person['id']}/daily-brief", {"as_of_date": "2026-08-19"}),
    ):
        response = await client.get(path, params=params, headers=headers)
        assert response.status_code == 401, path
        assert response.json()["code"] == "NOT_AUTHENTICATED", path


async def test_revoked_bearer_token_loses_access_to_the_read_endpoints(
    client, sessionmaker, lukas_payload
) -> None:
    person = await _seed_person(client, sessionmaker, "revoked@example.com", lukas_payload)
    headers = await _bearer_headers(client, "revoked@example.com")
    assert (await client.post("/v1/auth/mobile/logout", headers=headers)).status_code == 204

    for path, params in (
        ("/v1/people", None),
        (f"/v1/people/{person['id']}/timing", {"as_of_date": "2026-08-19"}),
        (f"/v1/people/{person['id']}/daily-brief", {"as_of_date": "2026-08-19"}),
    ):
        response = await client.get(path, params=params, headers=headers)
        assert response.status_code == 401, path
        assert response.json()["code"] == "NOT_AUTHENTICATED", path


async def test_bearer_token_cannot_read_a_foreign_person(
    client, sessionmaker, lukas_payload
) -> None:
    """Ownership is resolved by the same repository lookup the cookie path uses, so a
    foreign person must be indistinguishable from a non-existent one (404)."""
    victim = await _seed_person(client, sessionmaker, "owner@example.com", lukas_payload)
    await _seed_user(sessionmaker, "attacker@example.com")
    headers = await _bearer_headers(client, "attacker@example.com")

    for person_id in (victim["id"], str(uuid.uuid4())):
        timing = await client.get(
            f"/v1/people/{person_id}/timing",
            params={"as_of_date": "2026-08-19"},
            headers=headers,
        )
        assert timing.status_code == 404
        brief = await client.get(
            f"/v1/people/{person_id}/daily-brief",
            params={"as_of_date": "2026-08-19"},
            headers=headers,
        )
        assert brief.status_code == 404

    people = await client.get("/v1/people", headers=headers)
    assert people.status_code == 200
    assert people.json() == []

    # The widened dependency must stay scoped: mutations and unrelated reads keep
    # requiring the browser session, so a stolen bearer token cannot write.
    # The CSRF gate runs ahead of authentication on mutating routes, so a bearer-only
    # write is stopped there (403) rather than at the auth layer (401) -- either way it
    # never reaches the handler.
    created = await client.post(
        f"/v1/people/{victim['id']}/calculations",
        json={"as_of_date": "2026-08-19"},
        headers=headers,
    )
    assert created.status_code == 403
    assert created.json()["code"] == "CSRF_VALIDATION_FAILED"

    unrelated_read = await client.get("/v1/me/entitlements", headers=headers)
    assert unrelated_read.status_code == 401
    assert unrelated_read.json()["code"] == "NOT_AUTHENTICATED"
