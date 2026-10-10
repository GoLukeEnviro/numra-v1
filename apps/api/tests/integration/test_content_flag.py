"""D6 (1/2): the read-time `content_flag` on reports, report sections and relationship
analyses. Defective legacy content is simulated by writing a token into an otherwise
COMPLETE result directly in the database -- the state production holds from before the
persistence gate (#315) existed."""

from __future__ import annotations

import copy
import datetime as dt
import uuid

import pytest
from sqlalchemy import select

from numra_api.analysis_worker import run_one_cycle as run_analysis_cycle
from numra_api.auth.passwords import hash_password
from numra_api.cli import build_parser
from numra_api.models import RelationshipAnalysis, Report, ReportSection
from numra_api.models.enums import UserRole
from numra_api.repositories.users import create_user, mark_email_verified, set_user_role
from numra_api.services.content_flag import payload_flag
from numra_api.services.content_flag_scan import scan_stored_content
from numra_api.worker import run_one_cycle

pytestmark = pytest.mark.integration

TOKEN = "Das ist {{metric:a:life_path}} im Satz."


async def _login(client, sessionmaker, email: str) -> dict:
    async with sessionmaker() as db:
        user = await create_user(db, email=email, password_hash=hash_password("password12345"))
        await mark_email_verified(db, user=user, verified_at=dt.datetime.now(dt.UTC))
        await db.commit()
    return await _switch_user(client, email)


async def _switch_user(client, email: str) -> dict:
    await client.post("/v1/auth/logout")
    response = await client.post(
        "/v1/auth/login", json={"email": email, "password": "password12345"}
    )
    assert response.status_code == 200
    return {"x-csrf-token": client.cookies["numra_csrf"]}


async def _complete_report(client, sessionmaker, llm, headers, payload) -> str:
    person = (await client.post("/v1/people", json=payload, headers=headers)).json()
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
    assert await run_one_cycle(sessionmaker, llm=llm) is True
    return report["id"]


async def _poison_report(sessionmaker, report_id: str, *, section_index: int = 0) -> str:
    """Put TOKEN into the summary of one section (content_json and the report_sections row).
    Returns the section_id."""
    async with sessionmaker() as db:
        report = await db.get(Report, uuid.UUID(report_id))
        content = copy.deepcopy(report.content_json)
        content["sections"][section_index]["summary"] = TOKEN
        report.content_json = content
        section_id = content["sections"][section_index]["section_id"]
        row = (
            await db.execute(
                select(ReportSection).where(
                    ReportSection.report_id == report.id, ReportSection.section_id == section_id
                )
            )
        ).scalar_one()
        row.content_json = content["sections"][section_index]
        await db.commit()
        return section_id


async def _stored_content(sessionmaker, report_id: str) -> dict:
    async with sessionmaker() as db:
        report = await db.get(Report, uuid.UUID(report_id))
        return copy.deepcopy(report.content_json)


async def test_clean_report_has_no_flag(client, sessionmaker, llm, lukas_payload) -> None:
    headers = await _login(client, sessionmaker, "flag-clean@example.com")
    report_id = await _complete_report(client, sessionmaker, llm, headers, lukas_payload)

    body = (await client.get(f"/v1/reports/{report_id}")).json()

    assert body["content_flag"] == "none"
    assert body["flagged_section_ids"] == []


async def test_only_the_actually_affected_section_is_flagged_and_text_is_verbatim(
    client, sessionmaker, llm, lukas_payload
) -> None:
    headers = await _login(client, sessionmaker, "flag-section@example.com")
    report_id = await _complete_report(client, sessionmaker, llm, headers, lukas_payload)
    section_id = await _poison_report(sessionmaker, report_id, section_index=2)
    stored = await _stored_content(sessionmaker, report_id)

    body = (await client.get(f"/v1/reports/{report_id}")).json()

    assert body["content_flag"] == "unresolved_template_tokens"
    assert body["flagged_section_ids"] == [section_id]
    assert body["content"] == stored  # the defective text is shown as stored, not repaired
    assert body["content"]["sections"][2]["summary"] == TOKEN
    [summary] = (await client.get("/v1/reports")).json()
    assert "content_flag" not in summary  # lists never scan (see services/content_flag.py)
    assert await _stored_content(sessionmaker, report_id) == stored  # reading wrote nothing


async def test_age_alone_does_not_flag(client, sessionmaker, llm, lukas_payload) -> None:
    headers = await _login(client, sessionmaker, "flag-old@example.com")
    report_id = await _complete_report(client, sessionmaker, llm, headers, lukas_payload)
    async with sessionmaker() as db:
        report = await db.get(Report, uuid.UUID(report_id))
        report.created_at = dt.datetime(2020, 1, 1, tzinfo=dt.UTC)
        report.generated_at = dt.datetime(2020, 1, 1, tzinfo=dt.UTC)
        report.prompt_version = "numra-report-v1"
        await db.commit()

    assert (await client.get(f"/v1/reports/{report_id}")).json()["content_flag"] == "none"


async def test_token_outside_the_sections_flags_the_report_only(
    client, sessionmaker, llm, lukas_payload
) -> None:
    headers = await _login(client, sessionmaker, "flag-toplevel@example.com")
    report_id = await _complete_report(client, sessionmaker, llm, headers, lukas_payload)
    async with sessionmaker() as db:
        report = await db.get(Report, uuid.UUID(report_id))
        content = copy.deepcopy(report.content_json)
        content["model_name"] = "{{metric:a:life_path}}"
        report.content_json = content
        await db.commit()

    body = (await client.get(f"/v1/reports/{report_id}")).json()

    assert body["content_flag"] == "unresolved_template_tokens"
    assert body["flagged_section_ids"] == []


async def test_oversize_text_is_flagged_fail_closed(
    client, sessionmaker, llm, lukas_payload
) -> None:
    headers = await _login(client, sessionmaker, "flag-oversize@example.com")
    report_id = await _complete_report(client, sessionmaker, llm, headers, lukas_payload)
    async with sessionmaker() as db:
        report = await db.get(Report, uuid.UUID(report_id))
        content = copy.deepcopy(report.content_json)
        content["sections"][0]["text"] = "Wort " * 7000
        report.content_json = content
        await db.commit()

    body = (await client.get(f"/v1/reports/{report_id}")).json()

    assert body["content_flag"] == "unresolved_template_tokens"
    assert body["flagged_section_ids"] == [content["sections"][0]["section_id"]]


def test_lenient_report_mode_keeps_plain_braces_but_analyses_are_strict() -> None:
    prose = {"text": "Eine einzelne Klammer { im Satz."}

    assert payload_flag(prose, strict_braces=False).value == "none"
    assert payload_flag(prose, strict_braces=True).value == "unresolved_template_tokens"


async def test_foreign_user_and_admin_get_404_and_no_flag(
    client, sessionmaker, llm, lukas_payload
) -> None:
    headers = await _login(client, sessionmaker, "flag-owner@example.com")
    report_id = await _complete_report(client, sessionmaker, llm, headers, lukas_payload)
    await _poison_report(sessionmaker, report_id)

    await _login(client, sessionmaker, "flag-stranger@example.com")
    stranger = await client.get(f"/v1/reports/{report_id}")
    assert stranger.status_code == 404
    assert "content_flag" not in stranger.text
    assert (await client.get("/v1/reports")).json() == []

    async with sessionmaker() as db:
        admin = await create_user(
            db, email="flag-admin@example.com", password_hash=hash_password("password12345")
        )
        await set_user_role(db, user=admin, role=UserRole.ADMIN)
        await db.commit()
    await _switch_user(client, "flag-admin@example.com")
    assert (await client.get(f"/v1/reports/{report_id}")).status_code == 404
    assert (await client.get("/v1/reports")).json() == []


async def test_unauthenticated_gets_401(client, sessionmaker, llm, lukas_payload) -> None:
    headers = await _login(client, sessionmaker, "flag-anon@example.com")
    report_id = await _complete_report(client, sessionmaker, llm, headers, lukas_payload)
    assert (await client.post("/v1/auth/logout", headers=headers)).status_code in (200, 204)

    assert (await client.get(f"/v1/reports/{report_id}")).status_code == 401


# --- relationship analyses ------------------------------------------------------------


async def _set_up_partner_workspace(
    client, sessionmaker, lukas_payload, email_a: str, email_b: str
) -> tuple[str, dict, dict]:
    """Two connected users with a SELF profile + calculation each, workspace type PARTNER
    (same set-up as test_relationship_analysis.py). Returns (workspace_id, headers_a,
    headers_b)."""
    headers_a = await _login(client, sessionmaker, email_a)
    invitation = (
        await client.post("/v1/connections/invitations", json={"method": "LINK"}, headers=headers_a)
    ).json()
    headers_b = await _login(client, sessionmaker, email_b)
    redeem = await client.post(
        "/v1/connections/invitations/redeem",
        json={"token": invitation["token"]},
        headers=headers_b,
    )
    assert redeem.status_code == 201
    workspace_id = redeem.json()["workspace_id"]
    await _create_self_person(client, headers_b, lukas_payload)
    headers_a = await _switch_user(client, email_a)
    await _create_self_person(
        client,
        headers_a,
        {**lukas_payload, "birth_first_names": "Partner", "birth_last_name": "Eins"},
    )
    patch = await client.patch(
        f"/v1/workspaces/{workspace_id}",
        json={"relationship_type": "PARTNER"},
        headers=headers_a,
    )
    assert patch.status_code == 200
    return workspace_id, headers_a, headers_b


async def _create_self_person(client, headers: dict, payload: dict) -> None:
    response = await client.post("/v1/people", json=payload, headers=headers)
    assert response.status_code == 201
    calc = await client.post(
        f"/v1/people/{response.json()['id']}/calculations",
        json={"as_of_date": "2026-08-19"},
        headers=headers,
    )
    assert calc.status_code == 201


async def _complete_analysis(client, sessionmaker, llm, lukas_payload, tag: str):
    workspace_id, headers_a, _headers_b = await _set_up_partner_workspace(
        client, sessionmaker, lukas_payload, f"{tag}-a@example.com", f"{tag}-b@example.com"
    )
    created = await client.post(
        f"/v1/workspaces/{workspace_id}/relationship-analysis", json={}, headers=headers_a
    )
    assert created.status_code == 201
    assert await run_analysis_cycle(sessionmaker, llm=llm) is True
    return workspace_id, created.json()["id"], headers_a


async def _poison_analysis(sessionmaker, analysis_id: str) -> dict:
    async with sessionmaker() as db:
        analysis = await db.get(RelationshipAnalysis, uuid.UUID(analysis_id))
        result = copy.deepcopy(analysis.result_json)
        statement = result["dimensions"][0]["statements"][0]
        statement["text"] = "Ein Rest [a:life_path] im Satz."
        analysis.result_json = result
        await db.commit()
        return result


async def test_relationship_analysis_flag_is_set_only_when_affected(
    client, sessionmaker, llm, lukas_payload
) -> None:
    workspace_id, analysis_id, headers_a = await _complete_analysis(
        client, sessionmaker, llm, lukas_payload, "flag-ra"
    )
    url = f"/v1/workspaces/{workspace_id}/relationship-analysis/{analysis_id}"

    assert (await client.get(url, headers=headers_a)).json()["content_flag"] == "none"

    stored = await _poison_analysis(sessionmaker, analysis_id)
    body = (await client.get(url, headers=headers_a)).json()
    latest = (
        await client.get(f"/v1/workspaces/{workspace_id}/relationship-analysis", headers=headers_a)
    ).json()

    assert body["content_flag"] == latest["content_flag"] == "unresolved_template_tokens"
    assert body["result"] == stored


async def test_relationship_analysis_flag_follows_the_read_access_rules(
    client, sessionmaker, llm, lukas_payload
) -> None:
    workspace_id, analysis_id, _headers_a = await _complete_analysis(
        client, sessionmaker, llm, lukas_payload, "flag-ra-idor"
    )
    await _poison_analysis(sessionmaker, analysis_id)
    url = f"/v1/workspaces/{workspace_id}/relationship-analysis/{analysis_id}"

    await _login(client, sessionmaker, "flag-ra-outsider@example.com")
    outsider = await client.get(url)
    assert outsider.status_code == 404
    assert "content_flag" not in outsider.text

    # An old result stays a readable historical snapshot after a consent revoke (existing
    # rule, test_old_analysis_stays_readable_after_consent_revoke) -- and with it the
    # verdict, which reveals nothing the text does not.
    headers_b = await _switch_user(client, "flag-ra-idor-b@example.com")
    revoke = await client.post(
        f"/v1/workspaces/{workspace_id}/consent/revoke",
        json={"scope": "RELATIONSHIP_INSIGHTS"},
        headers=headers_b,
    )
    assert revoke.status_code == 200
    after = await client.get(url)
    assert after.status_code == 200
    assert after.json()["content_flag"] == "unresolved_template_tokens"


# --- CLI / scan -----------------------------------------------------------------------


async def test_scan_counts_only_and_writes_nothing(
    client, sessionmaker, llm, lukas_payload
) -> None:
    headers = await _login(client, sessionmaker, "flag-scan@example.com")
    clean_id = await _complete_report(client, sessionmaker, llm, headers, lukas_payload)
    headers = await _switch_user(client, "flag-scan@example.com")
    other_person = {
        **lukas_payload,
        "birth_first_names": "Zweit",
        "person_account_mode": "MANAGED_OTHER",
    }
    bad_id = await _complete_report(client, sessionmaker, llm, headers, other_person)
    await _poison_report(sessionmaker, bad_id)
    before = {i: await _stored_content(sessionmaker, i) for i in (clean_id, bad_id)}

    async with sessionmaker() as db:
        scans = await scan_stored_content(db)

    assert scans["report"].checked == 2
    assert scans["report"].flagged_ids == [uuid.UUID(bad_id)]
    assert scans["report_section"].flagged == 1
    assert scans["relationship_analysis"].checked == 0
    assert {i: await _stored_content(sessionmaker, i) for i in (clean_id, bad_id)} == before


def test_cli_offers_no_apply_and_no_regeneration() -> None:
    parser = build_parser()

    args = parser.parse_args(["content-flags", "scan", "--list-ids"])
    assert args.list_ids is True
    for forbidden in (["--apply"], ["--regenerate"]):
        with pytest.raises(SystemExit):
            parser.parse_args(["content-flags", "scan", *forbidden])
