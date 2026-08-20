"""Export/PDF product integration (P1): a real (not mocked) call to the apps/pdf
service, real file storage on disk via `LocalExportStorage`, and a download round-trip
that returns byte-identical content. See TEST_PDF_URL/TEST_PDF_TOKEN in conftest.py --
these tests require a running apps/pdf instance and fail with a clear connection error
if one isn't reachable, rather than silently skipping.
"""

from __future__ import annotations

import uuid

import pytest

from numra_api.auth.passwords import hash_password
from numra_api.repositories.users import create_user
from numra_api.worker import run_one_cycle

pytestmark = pytest.mark.integration


async def _login(client, sessionmaker, email: str) -> dict:
    async with sessionmaker() as db:
        await create_user(db, email=email, password_hash=hash_password("password12345"))
        await db.commit()
    response = await client.post(
        "/v1/auth/login", json={"email": email, "password": "password12345"}
    )
    assert response.status_code == 200
    return {"x-csrf-token": client.cookies["numra_csrf"]}


async def _create_complete_report(client, sessionmaker, llm, headers, lukas_payload) -> str:
    person = (await client.post("/v1/people", json=lukas_payload, headers=headers)).json()
    calc = (
        await client.post(
            f"/v1/people/{person['id']}/calculations",
            json={"as_of_date": "2026-01-01"},
            headers=headers,
        )
    ).json()
    report = (
        await client.post(
            "/v1/reports",
            json={"calculation_id": calc["id"], "report_type": "QUICK"},
            headers=headers,
        )
    ).json()
    claimed = await run_one_cycle(sessionmaker, llm=llm)
    assert claimed is True
    final_report = (await client.get(f"/v1/reports/{report['id']}", headers=headers)).json()
    assert final_report["status"] == "COMPLETE"
    return str(report["id"])


async def test_create_export_renders_real_pdf_and_downloads_it(
    client, sessionmaker, llm, lukas_payload
) -> None:
    headers = await _login(client, sessionmaker, "export-pdf@example.com")
    report_id = await _create_complete_report(client, sessionmaker, llm, headers, lukas_payload)

    create_response = await client.post(
        "/v1/exports", json={"report_id": report_id, "export_type": "pdf"}, headers=headers
    )
    assert create_response.status_code == 201
    export = create_response.json()
    assert export["status"] == "complete"
    assert export["export_type"] == "pdf"
    assert export["file_size_bytes"] is not None
    assert export["file_size_bytes"] > 1000  # a real rendered PDF, not an empty stub

    download_response = await client.get(f"/v1/exports/{export['id']}/download", headers=headers)
    assert download_response.status_code == 200
    assert download_response.headers["content-type"] == "application/pdf"
    assert download_response.content[:5] == b"%PDF-"
    assert len(download_response.content) == export["file_size_bytes"]


async def test_list_exports_returns_users_own_exports(
    client, sessionmaker, llm, lukas_payload
) -> None:
    headers = await _login(client, sessionmaker, "export-list@example.com")
    report_id = await _create_complete_report(client, sessionmaker, llm, headers, lukas_payload)

    await client.post(
        "/v1/exports", json={"report_id": report_id, "export_type": "pdf"}, headers=headers
    )
    listing = await client.get("/v1/exports", headers=headers)
    assert listing.status_code == 200
    body = listing.json()
    assert len(body) == 1
    assert body[0]["report_id"] == report_id


async def test_create_export_rejects_report_not_yet_complete(
    client, sessionmaker, lukas_payload
) -> None:
    headers = await _login(client, sessionmaker, "export-not-ready@example.com")
    person = (await client.post("/v1/people", json=lukas_payload, headers=headers)).json()
    calc = (
        await client.post(
            f"/v1/people/{person['id']}/calculations",
            json={"as_of_date": "2026-01-01"},
            headers=headers,
        )
    ).json()
    report = (
        await client.post(
            "/v1/reports",
            json={"calculation_id": calc["id"], "report_type": "QUICK"},
            headers=headers,
        )
    ).json()
    # No worker cycle run — report is still QUEUED/PENDING.
    response = await client.post(
        "/v1/exports", json={"report_id": report["id"], "export_type": "pdf"}, headers=headers
    )
    assert response.status_code == 409
    assert response.json()["code"] == "REPORT_NOT_READY"


async def test_create_export_rejects_report_belonging_to_another_user(
    client, sessionmaker, llm, lukas_payload
) -> None:
    owner_headers = await _login(client, sessionmaker, "export-owner@example.com")
    report_id = await _create_complete_report(
        client, sessionmaker, llm, owner_headers, lukas_payload
    )

    other_headers = await _login(client, sessionmaker, "export-other@example.com")
    response = await client.post(
        "/v1/exports",
        json={"report_id": report_id, "export_type": "pdf"},
        headers=other_headers,
    )
    assert response.status_code == 404


async def test_download_export_rejects_another_users_export(
    client, sessionmaker, llm, lukas_payload
) -> None:
    owner_headers = await _login(client, sessionmaker, "export-dl-owner@example.com")
    report_id = await _create_complete_report(
        client, sessionmaker, llm, owner_headers, lukas_payload
    )
    export = (
        await client.post(
            "/v1/exports",
            json={"report_id": report_id, "export_type": "pdf"},
            headers=owner_headers,
        )
    ).json()

    other_headers = await _login(client, sessionmaker, "export-dl-other@example.com")
    response = await client.get(f"/v1/exports/{export['id']}/download", headers=other_headers)
    assert response.status_code == 404


async def test_download_nonexistent_export_returns_404(client, sessionmaker) -> None:
    headers = await _login(client, sessionmaker, "export-404@example.com")
    response = await client.get(f"/v1/exports/{uuid.uuid4()}/download", headers=headers)
    assert response.status_code == 404
