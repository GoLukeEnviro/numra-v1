from __future__ import annotations

import pytest
from sqlalchemy import func, select

from numra_api.auth.passwords import hash_password
from numra_api.models import (
    Calculation,
    Export,
    LLMGeneration,
    Person,
    RelationshipComparison,
    Report,
    ReportJob,
    ReportSection,
    Session,
    User,
)
from numra_api.repositories.users import create_user
from numra_api.worker import run_one_cycle

pytestmark = pytest.mark.integration


async def _count(sessionmaker, model) -> int:
    async with sessionmaker() as db:
        result = await db.execute(select(func.count()).select_from(model))
        return int(result.scalar_one())


async def _login(client, sessionmaker, email: str) -> dict:
    async with sessionmaker() as db:
        await create_user(db, email=email, password_hash=hash_password("password12345"))
        await db.commit()
    response = await client.post(
        "/v1/auth/login", json={"email": email, "password": "password12345"}
    )
    assert response.status_code == 200
    return {"x-csrf-token": client.cookies["numra_csrf"]}


async def test_delete_all_cascades_every_table(client, sessionmaker, llm, lukas_payload) -> None:
    """master prompt §138: create a user, person, calculation, relationship, report,
    report job — then Delete All — and verify zero rows remain in every dependent
    table for that user, with no orphans."""
    email = "delete-me@example.com"
    headers = await _login(client, sessionmaker, email)

    person_a = (await client.post("/v1/people", json=lukas_payload, headers=headers)).json()
    other_payload = {**lukas_payload, "birth_first_names": "Second", "birth_last_name": "Person"}
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

    await client.post(
        "/v1/relationships",
        json={"calculation_a_id": calc_a["id"], "calculation_b_id": calc_b["id"]},
        headers=headers,
    )

    report_response = await client.post(
        "/v1/reports",
        json={"calculation_id": calc_a["id"], "report_type": "QUICK"},
        headers=headers,
    )
    assert report_response.status_code == 201

    # Run the job to completion so llm_generations / report_sections have a chance to
    # exist too (the pipeline itself doesn't write llm_generations rows in this phase —
    # see specs/evidence/phase-4.md — but report_sections and the completed report do).
    await run_one_cycle(sessionmaker, llm=llm)

    # Sanity: rows actually exist before deletion.
    assert await _count(sessionmaker, Person) >= 2
    assert await _count(sessionmaker, Calculation) >= 2
    assert await _count(sessionmaker, RelationshipComparison) >= 1
    assert await _count(sessionmaker, Report) >= 1
    assert await _count(sessionmaker, ReportJob) >= 1
    assert await _count(sessionmaker, ReportSection) >= 1

    delete_response = await client.post(
        "/v1/account/delete-all", json={"password": "password12345"}, headers=headers
    )
    assert delete_response.status_code == 204

    assert await _count(sessionmaker, User) == 0
    assert await _count(sessionmaker, Session) == 0
    assert await _count(sessionmaker, Person) == 0
    assert await _count(sessionmaker, Calculation) == 0
    assert await _count(sessionmaker, RelationshipComparison) == 0
    assert await _count(sessionmaker, Report) == 0
    assert await _count(sessionmaker, ReportJob) == 0
    assert await _count(sessionmaker, ReportSection) == 0
    assert await _count(sessionmaker, LLMGeneration) == 0
    assert await _count(sessionmaker, Export) == 0

    # Session cookie is now invalid — the API must not silently keep serving requests.
    me_response = await client.get("/v1/auth/me")
    assert me_response.status_code == 401


async def test_delete_all_requires_correct_password(client, sessionmaker) -> None:
    headers = await _login(client, sessionmaker, "wrong-pw@example.com")
    response = await client.post(
        "/v1/account/delete-all", json={"password": "totally-wrong"}, headers=headers
    )
    assert response.status_code == 401
    assert response.json()["code"] == "INVALID_CREDENTIALS"
    # User must still exist.
    assert await _count(sessionmaker, User) >= 1


async def test_delete_all_requires_csrf(client, sessionmaker) -> None:
    await _login(client, sessionmaker, "no-csrf@example.com")
    response = await client.post("/v1/account/delete-all", json={"password": "password12345"})
    assert response.status_code == 403
