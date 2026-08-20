from __future__ import annotations

import datetime as dt

import pytest

from numra_api.auth.passwords import hash_password
from numra_api.models.enums import ReportJobStatus
from numra_api.repositories.reports import claim_next_job
from numra_api.repositories.users import create_user
from numra_api.worker import run_one_cycle

pytestmark = pytest.mark.integration


async def _login(client, sessionmaker, email: str = "reports@example.com") -> dict:
    async with sessionmaker() as db:
        await create_user(db, email=email, password_hash=hash_password("password12345"))
        await db.commit()
    response = await client.post(
        "/v1/auth/login", json={"email": email, "password": "password12345"}
    )
    assert response.status_code == 200
    return {"x-csrf-token": client.cookies["numra_csrf"]}


async def _create_person_and_calculation(client, headers, lukas_payload) -> str:
    person = (await client.post("/v1/people", json=lukas_payload, headers=headers)).json()
    calc = (
        await client.post(
            f"/v1/people/{person['id']}/calculations",
            json={"as_of_date": "2026-01-01"},
            headers=headers,
        )
    ).json()
    return calc["id"]


async def test_report_job_completes_via_worker(client, sessionmaker, llm, lukas_payload) -> None:
    headers = await _login(client, sessionmaker)
    calc_id = await _create_person_and_calculation(client, headers, lukas_payload)

    create_response = await client.post(
        "/v1/reports", json={"calculation_id": calc_id, "report_type": "QUICK"}, headers=headers
    )
    assert create_response.status_code == 201
    report = create_response.json()
    assert report["status"] == "PENDING"
    job_id = report["job_id"]

    job_response = await client.get(f"/v1/report-jobs/{job_id}", headers=headers)
    assert job_response.json()["status"] == "QUEUED"

    claimed = await run_one_cycle(sessionmaker, llm=llm)
    assert claimed is True

    final_job = (await client.get(f"/v1/report-jobs/{job_id}", headers=headers)).json()
    assert final_job["status"] == "COMPLETE"
    assert final_job["progress"] == 100

    final_report = (await client.get(f"/v1/reports/{report['id']}", headers=headers)).json()
    assert final_report["status"] == "COMPLETE"
    assert final_report["content"] is not None
    assert final_report["content"]["total_word_count"] > 0
    assert len(final_report["content"]["sections"]) >= 10


async def test_report_idempotency_key_returns_same_job(client, sessionmaker, lukas_payload) -> None:
    headers = await _login(client, sessionmaker, email="idem@example.com")
    calc_id = await _create_person_and_calculation(client, headers, lukas_payload)

    idem_headers = {**headers, "Idempotency-Key": "same-key-123"}
    first = await client.post(
        "/v1/reports",
        json={"calculation_id": calc_id, "report_type": "QUICK"},
        headers=idem_headers,
    )
    second = await client.post(
        "/v1/reports",
        json={"calculation_id": calc_id, "report_type": "QUICK"},
        headers=idem_headers,
    )
    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["id"] == second.json()["id"]
    assert first.json()["job_id"] == second.json()["job_id"]


async def test_idempotency_key_is_scoped_per_user_not_global(
    client, sessionmaker, lukas_payload
) -> None:
    """P1 hardening: report_jobs.idempotency_key uniqueness is UNIQUE(user_id,
    idempotency_key), not a bare global UNIQUE(idempotency_key) -- two different users
    reusing the same idempotency-key string (e.g. both clients generated "same-key")
    must each get their own report, not collide with (or 500 on) the other's."""
    # The shared `client` fixture has one cookie jar: logging in as user B overwrites
    # user A's CSRF cookie, which would invalidate a header captured earlier from A's
    # login -- so user A's whole request (login, setup, create) must complete before
    # logging in as B.
    headers_a = await _login(client, sessionmaker, email="idem-user-a@example.com")
    calc_id_a = await _create_person_and_calculation(client, headers_a, lukas_payload)
    shared_key = "shared-idempotency-key"
    response_a = await client.post(
        "/v1/reports",
        json={"calculation_id": calc_id_a, "report_type": "QUICK"},
        headers={**headers_a, "Idempotency-Key": shared_key},
    )

    headers_b = await _login(client, sessionmaker, email="idem-user-b@example.com")
    calc_id_b = await _create_person_and_calculation(client, headers_b, lukas_payload)
    response_b = await client.post(
        "/v1/reports",
        json={"calculation_id": calc_id_b, "report_type": "QUICK"},
        headers={**headers_b, "Idempotency-Key": shared_key},
    )
    assert response_a.status_code == 201
    assert response_b.status_code == 201
    assert response_a.json()["id"] != response_b.json()["id"]
    assert response_a.json()["job_id"] != response_b.json()["job_id"]


async def test_worker_reclaims_job_with_expired_lease(sessionmaker) -> None:
    """Simulates a crashed worker: a job stuck in GENERATING with an expired lease must
    be reclaimable by another worker cycle (restart safety, master prompt §110)."""
    async with sessionmaker() as db:
        from numra_api.auth.passwords import hash_password
        from numra_api.models import Calculation, Person, Report, ReportJob, User

        user = User(email="restart@example.com", password_hash=hash_password("x12345678"))
        db.add(user)
        await db.flush()

        person = Person(
            user_id=user.id,
            birth_first_names="Test",
            birth_last_name="Person",
            birth_date=dt.date(1990, 1, 1),
        )
        db.add(person)
        await db.flush()

        calculation = Calculation(
            person_id=person.id,
            calculation_version="1.0.0",
            schema_version="1.0.0",
            as_of_date=dt.date(2026, 1, 1),
            input_snapshot={},
            canonical_profile_json={
                "schema_version": "1.0.0",
                "calculation_system": "numra-canonical",
                "calculation_version": "1.0.0",
                "person": {"birth_date": "1990-01-01"},
                "normalization": {
                    "original": "Test Person",
                    "components": ["TEST", "PERSON"],
                    "calculation_string": "TESTPERSON",
                },
                "core_numbers": {},
                "cycles": {},
                "timing": {},
                "diagnostics": {},
                "warnings": [],
            },
            deterministic_hash="0" * 64,
        )
        db.add(calculation)
        await db.flush()

        report = Report(
            user_id=user.id,
            calculation_id=calculation.id,
            report_type="QUICK",
            calculation_version="1.0.0",
            knowledge_version="1.0.0",
            prompt_version="numra-report-v1",
            profile_snapshot={},
            report_schema_version="1.0.0",
            status="PENDING",
        )
        db.add(report)
        await db.flush()

        stuck_job = ReportJob(
            report_id=report.id,
            user_id=user.id,
            status=ReportJobStatus.GENERATING,
            locked_at=dt.datetime.now(dt.UTC) - dt.timedelta(minutes=20),
            lease_until=dt.datetime.now(dt.UTC) - dt.timedelta(minutes=15),
            attempt_count=1,
        )
        db.add(stuck_job)
        await db.commit()

        reclaimed = await claim_next_job(db, now=dt.datetime.now(dt.UTC), lease_seconds=300)
        assert reclaimed is not None
        assert reclaimed.id == stuck_job.id
        assert reclaimed.attempt_count == 2
        await db.commit()
