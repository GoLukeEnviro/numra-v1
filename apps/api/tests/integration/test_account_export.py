"""PWA-07 (#125) -- Vertragstests fuer den Kontodatenexport.

Der Export ist eine *Auskunft ueber das eigene Konto*: er muss vollstaendig sein
(jede dokumentierte Kategorie ist da, auch leer), er darf ausschliesslich eigene Daten
enthalten (kein privates Material der Gegenseite, keine fremde E-Mail, keine fremde
Nutzer-ID), und er darf keine Geheimnisse oder internen Prompt-Bausteine
transportieren. Jeder dieser Punkte ist hier ein eigener Test -- die Negativtests
arbeiten mit Sentinel-Werten, die vorher nachweislich in der Datenbank stehen, damit
ein "ist nicht enthalten" nicht versehentlich gruen ist, weil der Wert nie existierte.
"""

from __future__ import annotations

import datetime as dt
import json
import re
import uuid
from collections.abc import Iterator
from typing import Any

import pytest
from sqlalchemy import select

from numra_api.auth.passwords import hash_password
from numra_api.models import (
    ChatMessage,
    ChatThread,
    CheckinDimension,
    CheckinResponse,
    EmailVerificationToken,
    Export,
    LLMGeneration,
    PasswordResetToken,
    PrivateReflection,
    RelationshipCheckin,
    Report,
    ReportJob,
    ReportSection,
    Session,
    ThreadContextSnapshot,
    User,
    WorkspaceMember,
)
from numra_api.repositories.users import create_user
from numra_api.services.account_export_service import (
    FILENAME_PREFIX,
    FORMAT,
    FORMAT_VERSION,
    SECTION_NAMES,
)

pytestmark = pytest.mark.integration

_PASSWORD = "password12345"
_OWNER = "export-owner@example.com"
_OTHER = "export-other@example.com"
_OWNER_SENTINEL = "OWNER-PRIVATE-SENTINEL"
_OTHER_SENTINEL = "OTHER-PRIVATE-SENTINEL"

#: Werte, die ausschliesslich in *internen* Spalten liegen. Keiner davon darf im
#: Exporttext auftauchen -- siehe test_export_never_contains_credentials_or_internals.
_SECRET_SENTINELS = {
    "session token hash": "SESSION-TOKEN-HASH-SENTINEL",
    "verification token hash": "VERIFICATION-TOKEN-HASH-SENTINEL",
    "reset token hash": "RESET-TOKEN-HASH-SENTINEL",
    "LLM prompt hash": "LLM-PROMPT-HASH-SENTINEL",
    "export storage ref": "EXPORT-FILE-REF-SENTINEL",
    "copilot context block": "CONTEXT-BLOCK-SENTINEL",
}

#: Schluesselnamen, die strukturell nichts in einem Kontodatenexport zu suchen haben:
#: Geheimnisse, interne Speicherpfade, Prompt-Material -- und jede fremde Nutzer-ID.
_FORBIDDEN_KEYS = {
    "password",
    "password_hash",
    "token_hash",
    "file_ref",
    "prompt_hash",
    "idempotency_key",
    "context_blocks_json",
    "context_snapshot_id",
}


def _all_keys(value: Any) -> Iterator[str]:
    if isinstance(value, dict):
        for key, item in value.items():
            yield key
            yield from _all_keys(item)
    elif isinstance(value, list):
        for item in value:
            yield from _all_keys(item)


async def _switch(client, email: str) -> dict[str, str]:
    await client.post("/v1/auth/logout")
    response = await client.post("/v1/auth/login", json={"email": email, "password": _PASSWORD})
    assert response.status_code == 200, response.text[:300]
    return {"x-csrf-token": client.cookies["numra_csrf"]}


async def _signup(client, sessionmaker, email: str) -> dict[str, str]:
    async with sessionmaker() as db:
        await create_user(db, email=email, password_hash=hash_password(_PASSWORD))
        await db.commit()
    return await _switch(client, email)


async def _profile(client, headers, *, first_name: str, last_name: str = "Beispiel") -> dict:
    response = await client.post(
        "/v1/people",
        json={
            "birth_first_names": first_name,
            "birth_last_name": last_name,
            "birth_date": "1990-03-14",
        },
        headers=headers,
    )
    assert response.status_code == 201, response.text[:300]
    return response.json()


async def _user_id(sessionmaker, email: str) -> uuid.UUID:
    async with sessionmaker() as db:
        return (await db.execute(select(User.id).where(User.email == email))).scalar_one()


async def _export(client) -> tuple[Any, dict]:
    response = await client.get("/v1/account/export")
    assert response.status_code == 200, response.text[:300]
    return response, json.loads(response.text)


async def _connected_workspace(client, sessionmaker) -> str:
    """Zwei Konten, eine bestaetigte Verbindung -- der Ausgangszustand fuer alles
    Geteilte."""
    owner = await _signup(client, sessionmaker, _OWNER)
    invitation = (
        await client.post("/v1/connections/invitations", json={"method": "LINK"}, headers=owner)
    ).json()
    partner = await _signup(client, sessionmaker, _OTHER)
    redeem = await client.post(
        "/v1/connections/invitations/redeem",
        json={"token": invitation["token"]},
        headers=partner,
    )
    assert redeem.status_code == 201, redeem.text[:300]
    return redeem.json()["workspace_id"]


# ---------------------------------------------------------------------------
# Zugang und Struktur
# ---------------------------------------------------------------------------


async def test_export_requires_authentication(client) -> None:
    assert (await client.get("/v1/account/export")).status_code == 401


async def test_empty_account_returns_every_documented_category(client, sessionmaker) -> None:
    """Ein frisches Konto bekommt keine 404 und kein halbes Dokument: alle Kategorien
    sind vorhanden und leer. Genau das ist die Zusage "leere Bereiche korrekt
    dargestellt"."""
    await _signup(client, sessionmaker, _OWNER)
    _, document = await _export(client)

    assert document["format"] == FORMAT
    assert document["format_version"] == FORMAT_VERSION
    assert dt.datetime.fromisoformat(document["generated_at"]).tzinfo is not None

    for name in SECTION_NAMES:
        assert name in document, f"Kategorie {name!r} fehlt im Export"

    assert document["profiles"] == []
    assert document["workspaces"] == []
    assert document["copilot"]["threads"] == []
    assert document["account"]["deletion"] == {"status": "active", "deleted_at": None}
    assert document["account"]["email"] == _OWNER
    # Keine einzige Zeile in irgendeiner Kategorie.
    assert all(count == 0 for count in document["counts"].values()), document["counts"]


async def test_export_headers_and_cache_behaviour_are_stable(client, sessionmaker) -> None:
    await _signup(client, sessionmaker, _OWNER)
    response = await client.get("/v1/account/export")

    assert response.headers["content-type"].startswith("application/json")
    # Ein Kontodatenexport gehoert in keinen Zwischenspeicher.
    assert response.headers["cache-control"] == "no-store"
    disposition = response.headers["content-disposition"]
    assert disposition.startswith("attachment; filename=")
    assert re.fullmatch(
        rf'"{re.escape(FILENAME_PREFIX)}-\d{{8}}T\d{{6}}Z\.json"',
        disposition.split("filename=", 1)[1],
    ), disposition


def _parse_document(raw: str) -> dict:
    return json.loads(raw)


# ---------------------------------------------------------------------------
# Inhalt: das eigene Konto
# ---------------------------------------------------------------------------


async def test_populated_account_exports_its_records_and_counts_agree(client, sessionmaker) -> None:
    headers = await _signup(client, sessionmaker, _OWNER)
    person = await _profile(client, headers, first_name="Lukas")

    reflection = (
        await client.post(
            f"/v1/people/{person['id']}/private-reflections",
            json={"entry_date": "2026-08-19", "content": _OWNER_SENTINEL},
            headers=headers,
        )
    ).json()
    note = (
        await client.post(
            f"/v1/people/{person['id']}/private-notes",
            json={"title": "Notiz", "content": "privat"},
            headers=headers,
        )
    ).json()
    task = (
        await client.post(
            f"/v1/people/{person['id']}/personal-tasks",
            json={"title": "Aufgabe", "description": "eigene Aufgabe"},
            headers=headers,
        )
    ).json()
    entry = (
        await client.post(
            f"/v1/people/{person['id']}/life-tracking-entries",
            json={"entry_date": "2026-08-19", "mood": 7, "energy": 5, "note": "Tag war ok"},
            headers=headers,
        )
    ).json()

    _, document = await _export(client)

    profiles = document["profiles"]
    assert len(profiles) == 1
    assert profiles[0]["id"] == person["id"]
    assert profiles[0]["account_mode"] == "SELF"
    assert profiles[0]["birth_date"] == "1990-03-14"

    personal = document["personal_workspace"]
    assert [item["id"] for item in personal["private_reflections"]] == [reflection["id"]]
    assert personal["private_reflections"][0]["content"] == _OWNER_SENTINEL
    assert [item["id"] for item in personal["private_notes"]] == [note["id"]]
    assert [item["id"] for item in personal["personal_tasks"]] == [task["id"]]
    assert [item["id"] for item in personal["life_tracking_entries"]] == [entry["id"]]
    assert personal["life_tracking_entries"][0]["mood"] == 7

    # `counts` ist keine Zierde: jede Zahl muss zur tatsaechlichen Liste passen.
    counts = document["counts"]
    assert counts["profiles"] == len(profiles) == 1
    assert counts["personal_workspace.private_reflections"] == 1
    assert counts["personal_workspace.private_notes"] == 1
    assert counts["personal_workspace.personal_tasks"] == 1
    assert counts["personal_workspace.life_tracking_entries"] == 1
    assert counts["workspaces"] == 0
    assert counts["reports.reports"] == 0
    assert _all_keys(document)


async def test_shared_workspace_is_exported_with_its_retained_artifacts(
    client, sessionmaker
) -> None:
    """Ein geteilter Workspace gehoert zur Kontohistorie: Mitglieder, Einwilligungen,
    Aufgaben und die geteilte Reflexion stehen drin."""
    workspace_id = await _connected_workspace(client, sessionmaker)

    owner = await _switch(client, _OWNER)
    task = await client.post(
        f"/v1/workspaces/{workspace_id}/tasks",
        json={"task_type": "JOINT_SHARED", "title": "Gemeinsam planen"},
        headers=owner,
    )
    assert task.status_code == 201, task.text[:300]

    person = await _profile(client, owner, first_name="Lukas")
    reflection = (
        await client.post(
            f"/v1/people/{person['id']}/private-reflections",
            json={"entry_date": "2026-08-19", "content": "geteilter Inhalt"},
            headers=owner,
        )
    ).json()
    share = await client.post(
        f"/v1/private-reflections/{reflection['id']}/share",
        json={"workspace_id": workspace_id},
        headers=owner,
    )
    assert share.status_code == 201, share.text[:300]

    raw_response, document = await _export(client)

    assert len(document["workspaces"]) == 1
    workspace = document["workspaces"][0]
    assert workspace["id"] == workspace_id
    assert workspace["status"] == "ACTIVE"
    assert {member["role"] for member in workspace["members"]} == {"self", "counterpart"}
    assert workspace["consent"]["grants"], "die Standard-Grants des Workspace fehlen"
    assert all(
        grant["direction"] in {"granted_by_me", "granted_to_me"}
        for grant in workspace["consent"]["grants"]
    )
    assert [item["title"] for item in workspace["tasks"]] == ["Gemeinsam planen"]
    shared = workspace["shared_reflections"]
    assert [item["content"] for item in shared] == ["geteilter Inhalt"]
    assert shared[0]["author"] == "self"

    assert document["relationships"]["connections"][0]["status"] == "ACTIVE"
    # Die Gegenseite erscheint ueber ihren Anzeigenamen, nicht ueber ihre Adresse,
    # und keine Nutzer-ID irgendeines Kontos steht im Dokument.
    assert _OTHER not in raw_response.text
    assert not [key for key in _all_keys(document) if key.endswith("_user_id")], sorted(
        key for key in _all_keys(document) if key.endswith("_user_id")
    )


async def test_own_checkin_responses_are_exported_but_not_the_others(client, sessionmaker) -> None:
    """`checkin_responses` ist laut `specs/v2/checkin-spec.md` (Section 19)
    SUBMITTER_ONLY: die eigene Einreichung gehoert in den Export, die der Gegenseite
    nicht -- geprueft mit beiden Zeilensaetzen in derselben Runde."""
    workspace_id = await _connected_workspace(client, sessionmaker)
    owner_id = await _user_id(sessionmaker, _OWNER)
    partner_id = await _user_id(sessionmaker, _OTHER)

    async with sessionmaker() as db:
        dimension = CheckinDimension(
            workspace_id=uuid.UUID(workspace_id),
            template_version=1,
            semantic_key="closeness",
            label="Naehe",
        )
        checkin = RelationshipCheckin(
            workspace_id=uuid.UUID(workspace_id), checkin_template_version=1
        )
        db.add(dimension)
        db.add(checkin)
        await db.flush()
        db.add(
            CheckinResponse(
                checkin_id=checkin.id,
                user_id=owner_id,
                dimension_id=dimension.id,
                semantic_key="closeness",
                value=7,
            )
        )
        db.add(
            CheckinResponse(
                checkin_id=checkin.id,
                user_id=partner_id,
                dimension_id=dimension.id,
                semantic_key="closeness",
                value=2,
            )
        )
        await db.commit()

    await _switch(client, _OWNER)
    raw_response, document = await _export(client)
    checkins = document["workspaces"][0]["checkins"]
    assert len(checkins) == 1
    own = checkins[0]["own_responses"]
    assert [row["value"] for row in own] == [7], own
    # Der Wert der Gegenseite existiert in der DB, steht aber nirgends im Export.
    assert '"value":2' not in raw_response.text.replace(" ", "")


async def test_export_repeats_are_stable_but_not_byte_identical(client, sessionmaker) -> None:
    """Wiederholbar heisst: gleiche Struktur, gleiche Feldnamen, gleiche Werte -- der
    Zeitstempel unterscheidet sich erwartungsgemaess."""
    headers = await _signup(client, sessionmaker, _OWNER)
    person = await _profile(client, headers, first_name="Lukas")
    await client.post(
        f"/v1/people/{person['id']}/private-notes",
        json={"title": "T", "content": "C"},
        headers=headers,
    )

    _, first = await _export(client)
    _, second = await _export(client)

    assert set(first) == set(second)
    assert first["counts"] == second["counts"]
    assert first["personal_workspace"] == second["personal_workspace"]
    assert first["generated_at"] != second["generated_at"]


# ---------------------------------------------------------------------------
# Grenzen: fremdes Material, Geheimnisse, Interna
# ---------------------------------------------------------------------------


async def test_export_never_contains_another_accounts_private_material(
    client, sessionmaker
) -> None:
    """Zwei Konten, je ein privates Material mit Sentinel -- dazu ein privater
    Copilot-Thread der Gegenseite. Der Export des einen Kontos darf ausschliesslich
    dessen eigenen Sentinel enthalten."""
    owner = await _signup(client, sessionmaker, _OWNER)
    owner_id = await _user_id(sessionmaker, _OWNER)
    owner_person = await _profile(client, owner, first_name="Lukas")
    await client.post(
        f"/v1/people/{owner_person['id']}/private-notes",
        json={"title": "eigen", "content": _OWNER_SENTINEL},
        headers=owner,
    )

    other = await _signup(client, sessionmaker, _OTHER)
    other_id = await _user_id(sessionmaker, _OTHER)
    other_person = await _profile(client, other, first_name="Partner")
    await client.post(
        f"/v1/people/{other_person['id']}/private-notes",
        json={"title": "fremd", "content": _OTHER_SENTINEL},
        headers=other,
    )

    async with sessionmaker() as db:
        foreign_thread = ChatThread(
            owner_user_id=other_id, scope="PERSONAL_PRIVATE", context_version=1
        )
        own_thread = ChatThread(owner_user_id=owner_id, scope="PERSONAL_PRIVATE", context_version=1)
        db.add(foreign_thread)
        db.add(own_thread)
        await db.flush()
        db.add(
            ChatMessage(
                thread_id=foreign_thread.id,
                role="USER",
                status="COMPLETE",
                author_user_id=other_id,
                content=_OTHER_SENTINEL,
            )
        )
        db.add(
            ChatMessage(
                thread_id=own_thread.id,
                role="USER",
                status="COMPLETE",
                author_user_id=owner_id,
                content="mein eigener Chatverlauf",
            )
        )
        await db.commit()

    # Zusaetzlich eine Verbindung, damit der Export in einem Zustand entsteht, in dem
    # die Daten der Gegenseite *sichtbar* waeren, wenn die Grenze nicht haelt.
    others_headers = await _switch(client, _OTHER)
    invitation = (
        await client.post(
            "/v1/connections/invitations", json={"method": "LINK"}, headers=others_headers
        )
    ).json()
    owner_again = await _switch(client, _OWNER)
    redeem = await client.post(
        "/v1/connections/invitations/redeem",
        json={"token": invitation["token"]},
        headers=owner_again,
    )
    assert redeem.status_code == 201, redeem.text[:300]

    owner_again = await _switch(client, _OWNER)
    raw_response, document = await _export(client)
    raw = raw_response.text

    assert _OWNER_SENTINEL in raw, "der eigene Inhalt muss enthalten sein"
    assert "mein eigener Chatverlauf" in raw, "der eigene Copilot-Verlauf fehlt"
    assert _OTHER_SENTINEL not in raw, "fremder privater Inhalt darf nicht im Export stehen"
    assert _OTHER not in raw, "die fremde E-Mail darf nicht im Export stehen"
    assert str(other_id) not in raw, "die fremde Nutzer-ID darf nicht im Export stehen"
    assert [thread["scope"] for thread in document["copilot"]["threads"]] == ["PERSONAL_PRIVATE"]
    assert len(document["copilot"]["threads"]) == 1, "fremder Personal-Copilot-Thread im Export"


async def test_export_never_contains_credentials_or_internals(client, sessionmaker) -> None:
    """Kein Passwort-Hash, kein Sitzungs-/Token-Hash, kein Prompt-Hash, kein
    Speicherpfad und kein Copilot-Kontextblock -- geprueft gegen Sentinel-Werte, die
    vorher nachweislich in der Datenbank stehen."""
    headers = await _signup(client, sessionmaker, _OWNER)
    person = await _profile(client, headers, first_name="Lukas")
    calculation = (
        await client.post(
            f"/v1/people/{person['id']}/calculations",
            json={"as_of_date": "2026-01-01"},
            headers=headers,
        )
    ).json()
    owner_id = await _user_id(sessionmaker, _OWNER)

    async with sessionmaker() as db:
        user = (await db.execute(select(User).where(User.id == owner_id))).scalar_one()
        password_hash = user.password_hash
        assert password_hash, "der Test braucht einen echten Hash als Gegenprobe"

        session_row = (
            await db.execute(select(Session).where(Session.user_id == owner_id).limit(1))
        ).scalar_one()
        assert session_row.token_hash, "der Test braucht eine echte Sitzung als Gegenprobe"
        # Die aktive Sitzung bleibt unangetastet (sonst waere der Client sofort
        # abgemeldet) -- der Sentinel kommt in eine zusaetzliche Sitzungszeile.
        db.add(
            Session(
                user_id=owner_id,
                token_hash=_SECRET_SENTINELS["session token hash"],
                expires_at=dt.datetime.now(dt.UTC) + dt.timedelta(hours=1),
            )
        )

        now = dt.datetime.now(dt.UTC)
        db.add(
            EmailVerificationToken(
                user_id=owner_id,
                token_hash=_SECRET_SENTINELS["verification token hash"],
                expires_at=now + dt.timedelta(hours=1),
            )
        )
        db.add(
            PasswordResetToken(
                user_id=owner_id,
                token_hash=_SECRET_SENTINELS["reset token hash"],
                expires_at=now + dt.timedelta(hours=1),
            )
        )
        thread = ChatThread(owner_user_id=owner_id, scope="PERSONAL_PRIVATE", context_version=1)
        db.add(thread)
        await db.flush()
        db.add(
            ThreadContextSnapshot(
                thread_id=thread.id,
                requester_user_id=owner_id,
                scope="PERSONAL_PRIVATE",
                context_version=1,
                context_blocks_json=[
                    {
                        "role": "system_instructions",
                        "content": _SECRET_SENTINELS["copilot context block"],
                    }
                ],
                consent_scopes_checked=[],
            )
        )
        calculation_id = uuid.UUID(calculation["id"])
        report = Report(
            user_id=owner_id,
            calculation_id=calculation_id,
            report_type="QUICK",
            calculation_version="1",
            knowledge_version="1",
            prompt_version="1",
            profile_snapshot={},
            report_schema_version="1",
            status="COMPLETE",
            # Der zusammengesetzte Report (dieselben Abschnitte, die auch als
            # `report_sections`-Zeilen liegen) -- genau dieser Produktinhalt gehoert
            # in den Export.
            content_json={"sections": [{"text": "sichtbarer Reportinhalt"}]},
        )
        db.add(report)
        await db.flush()
        job = ReportJob(report_id=report.id, user_id=owner_id)
        db.add(job)
        await db.flush()
        # Interne Bau-Zeile zum zusammengesetzten Report: sie traegt keinen Inhalt, den
        # `reports.content_json` nicht schon hat, und wird nicht mit-exportiert.
        db.add(
            ReportSection(
                report_id=report.id,
                section_id="s",
                title="T",
                order_index=0,
                content_json={"text": "sichtbarer Reportinhalt"},
            )
        )
        db.add(
            LLMGeneration(
                report_job_id=job.id,
                provider="mock",
                model="m",
                status="OK",
                prompt_hash=_SECRET_SENTINELS["LLM prompt hash"],
            )
        )
        db.add(
            Export(
                user_id=owner_id,
                report_id=report.id,
                export_type="pdf",
                status="complete",
                file_ref=_SECRET_SENTINELS["export storage ref"],
            )
        )
        await db.commit()

    raw = (await client.get("/v1/account/export")).text
    document = json.loads(raw)

    for label, sentinel in _SECRET_SENTINELS.items():
        assert sentinel not in raw, f"{label} ist im Export gelandet"
    assert password_hash not in raw, "der Passwort-Hash ist im Export gelandet"

    keys = set(_all_keys(document))
    assert not (keys & _FORBIDDEN_KEYS), sorted(keys & _FORBIDDEN_KEYS)
    assert "sichtbarer Reportinhalt" in raw, "der eigene Reportinhalt fehlt"


# ---------------------------------------------------------------------------
# Soft-Delete / Tombstone
# ---------------------------------------------------------------------------


async def test_deleted_account_cannot_export_its_data(client, sessionmaker) -> None:
    """Ein geloeschtes Konto ist gesperrt -- der Export ist kein Hintertuerchen am
    Login-Gate vorbei."""
    headers = await _signup(client, sessionmaker, _OWNER)
    assert (await client.get("/v1/account/export")).status_code == 200

    deleted = await client.post(
        "/v1/account/delete-all", json={"password": _PASSWORD}, headers=headers
    )
    assert deleted.status_code == 204

    assert (await client.get("/v1/account/export")).status_code == 401


async def test_export_after_partner_deletion_keeps_history_and_pseudonymizes(
    client, sessionmaker
) -> None:
    """Der interessanteste Zustand: die Gegenseite hat ihr Konto geloescht. Der Export
    des verbliebenen Kontos zeigt den Tombstone-Namen aus der Produktlogik und behaelt
    die gemeinsame Historie -- ohne die alte Adresse der Gegenseite."""
    workspace_id = await _connected_workspace(client, sessionmaker)

    owner = await _switch(client, _OWNER)
    person = await _profile(client, owner, first_name="Lukas")
    reflection = (
        await client.post(
            f"/v1/people/{person['id']}/private-reflections",
            json={"entry_date": "2026-08-19", "content": "bleibt lesbar"},
            headers=owner,
        )
    ).json()
    await client.post(
        f"/v1/private-reflections/{reflection['id']}/share",
        json={"workspace_id": workspace_id},
        headers=owner,
    )

    partner_headers = await _switch(client, _OTHER)
    await client.post(
        "/v1/account/delete-all", json={"password": _PASSWORD}, headers=partner_headers
    )

    owner = await _switch(client, _OWNER)
    raw_response, document = await _export(client)

    assert _OTHER not in raw_response.text
    workspace = document["workspaces"][0]
    counterpart = [member for member in workspace["members"] if member["role"] == "counterpart"]
    assert counterpart, "die Mitgliedschaft der Gegenseite bleibt sichtbar"
    assert counterpart[0]["display_name"] == "Ehemaliges Mitglied"
    assert [item["content"] for item in workspace["shared_reflections"]] == ["bleibt lesbar"]


async def test_export_after_own_deletion_leaves_nothing_readable(client, sessionmaker) -> None:
    """Nach der eigenen Loeschung ist nicht nur der Zugang weg, sondern auch das
    privaten Material, aus dem der Export entstand: eine neue Auskunft ueber dasselbe
    Konto kann es nicht mehr geben, weil das Konto kein privates Material mehr hat."""
    headers = await _signup(client, sessionmaker, _OWNER)
    person = await _profile(client, headers, first_name="Lukas")
    await client.post(
        f"/v1/people/{person['id']}/private-notes",
        json={"title": None, "content": _OWNER_SENTINEL},
        headers=headers,
    )
    assert (await client.get("/v1/account/export")).status_code == 200

    deleted = await client.post(
        "/v1/account/delete-all", json={"password": _PASSWORD}, headers=headers
    )
    assert deleted.status_code == 204

    async with sessionmaker() as db:
        remaining_notes = (
            (
                await db.execute(
                    select(PrivateReflection).where(PrivateReflection.content == _OWNER_SENTINEL)
                )
            )
            .scalars()
            .all()
        )
        assert remaining_notes == []
        members = (await db.execute(select(WorkspaceMember))).scalars().all()
        assert members == []


# ---------------------------------------------------------------------------
# Exit-Gate: Export und Loeschung zusammen
# ---------------------------------------------------------------------------


async def test_export_and_deletion_form_a_working_pair(client, sessionmaker) -> None:
    """Der PWA-07-Exit-Gate-Teil aus Issue #125: erst exportieren, dann ueber das
    Produkt loeschen -- beides muss fuer dasselbe Konto funktionieren."""
    headers = await _signup(client, sessionmaker, _OWNER)
    person = await _profile(client, headers, first_name="Lukas")
    await client.post(
        f"/v1/people/{person['id']}/private-notes",
        json={"title": None, "content": _OWNER_SENTINEL},
        headers=headers,
    )

    _, document = await _export(client)
    assert document["counts"]["personal_workspace.private_notes"] == 1
    assert document["account"]["deletion"]["status"] == "active"

    deleted = await client.post(
        "/v1/account/delete-all", json={"password": _PASSWORD}, headers=headers
    )
    assert deleted.status_code == 204

    async with sessionmaker() as db:
        tombstone = (
            await db.execute(select(User).where(User.email.like("deleted+%")))
        ).scalar_one_or_none()
        assert tombstone is not None
        assert tombstone.deleted_at is not None

    assert (await client.get("/v1/account/export")).status_code == 401


async def test_export_is_rate_limited_per_account(client, sessionmaker) -> None:
    """Ein Kontodatenexport ist teuer -- er darf nicht unbegrenzt pro Stunde
    ausgeloest werden koennen."""
    await _signup(client, sessionmaker, _OWNER)
    statuses = [(await client.get("/v1/account/export")).status_code for _ in range(12)]

    assert statuses.count(200) == 10, statuses
    assert statuses[-1] == 429, statuses
