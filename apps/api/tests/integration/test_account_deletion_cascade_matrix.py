"""PWA-07: die Retention-/Cascade-Matrix als erzwingbarer Vertrag.

ADR-013 legt die Policy in Prosa fest: beim Loeschen wird *privater* Inhalt entfernt,
*geteilte* Artefakte bleiben lesbar (mit dem geloeschten Nutzer pseudonymisiert), und
es darf keine verwaiste PII und keine fremden privaten Daten zurueckbleiben. Was fehlte,
war die Matrix pro Tabelle und ein Test, der sie erzwingt -- genau das liefert diese
Datei.

Die Vorgaenger-Tests in `test_account_deletion.py` pruefen einzelne Verhaltensweisen
(Partner sieht Pseudonym, Session tot, E-Mail wieder frei). Dieser Test prueft die
*Vollstaendigkeit*: jede Tabelle mit FK auf `users.id` wird klassifiziert, und die
globale referenzielle Integritaet wird ueber das ganze Schema geprueft. Damit faellt
sowohl eine vergessene Privat-Tabelle als auch ein dangling ForeignKey auf.
"""

from __future__ import annotations

import datetime as dt

import pytest
from sqlalchemy import func, select

from numra_api.auth.passwords import hash_password, verify_password
from numra_api.models import (
    AnalysisJob,
    Base,
    Calculation,
    ChatThread,
    CheckinDimension,
    CheckinIdempotency,
    CheckinResponse,
    ConsentEvent,
    ConsentGrant,
    EmailVerificationToken,
    EntitlementAssignment,
    Export,
    LifeTrackingEntry,
    PasswordResetToken,
    PatternAnalysis,
    PersonalTask,
    PrivateNote,
    PrivateReflection,
    RelationshipCheckin,
    RelationshipComparison,
    Report,
    ReportJob,
    Session,
    ThreadContextSnapshot,
    User,
    UserConnection,
    WorkspaceMember,
)
from numra_api.models.enums import ConnectionStatus, WorkspaceMemberStatus
from numra_api.repositories.users import create_user

pytestmark = pytest.mark.integration

_PASSWORD = "password12345"
_DELETED_OWNER = "matrix-owner@example.com"
_PARTNER = "matrix-partner@example.com"


def _expiry() -> dt.datetime:
    """Token-/Session-Zeilen brauchen ein `expires_at` (NOT NULL, kein Default)."""
    return dt.datetime.now(dt.UTC) + dt.timedelta(hours=1)


# ---------------------------------------------------------------------------
# Die Matrix. Jede Zeile ist eine Behauptung ueber eine Tabelle mit FK auf users.id.
# ---------------------------------------------------------------------------

#: Privater Inhalt. Muss nach der Loeschung fuer diesen Nutzer leer sein.
MUST_BE_EMPTY = [
    ("people", "user_id"),
    ("private_reflections", "user_id"),
    ("private_notes", "user_id"),
    ("personal_tasks", "user_id"),
    ("pattern_analyses", "user_id"),
    ("relationships", "user_id"),
    ("chat_threads", "owner_user_id"),
    ("reports", "user_id"),
    ("report_jobs", "user_id"),
    ("exports", "user_id"),
    ("sessions", "user_id"),
    ("email_verification_tokens", "user_id"),
    ("password_reset_tokens", "user_id"),
    ("life_tracking_entries", "user_id"),
    ("checkin_responses", "user_id"),
    ("thread_context_snapshots", "requester_user_id"),
]

#: Geteilte Historie bzw. Audit-Spur. Bleibt -- das ist die Zusage aus ADR-013.
#: Eine versehentliche Ueber-Loeschung (die den Partner blind macht) faellt hier auf.
MUST_BE_RETAINED = [
    ("user_connections", "user_a_id"),
    ("workspace_members", "user_id"),
    ("workspace_tasks", "proposer_user_id"),
    ("relationship_roadmaps", "proposer_user_id"),
    ("shared_reflections", "author_user_id"),
    ("consent_grants", "grantor_user_id"),
    ("consent_events", "actor_user_id"),
    ("connection_invitations", "inviter_user_id"),
    ("task_acceptances", "actor_user_id"),
    # Ausdruecklich als erhaltener geteilter FK dokumentiert (repositories/account.py,
    # Modul-Docstring): der Partner soll sehen, dass eine Analyse gelaufen ist.
    ("analysis_jobs", "requested_by_user_id"),
    # Bewusst NICHT geloescht -- beide tragen keinen Inhalt:
    #   * `entitlement_assignments` haengt am ueberlebenden Tombstone; PR-V2-10 loescht
    #     nur inhaltstragende Privatdaten (so steht es begruendet in
    #     `test_delete_all.py`: "traegt keine PII ... PR-V2-10 loescht bewusst nur
    #     inhaltstragende Privatdaten").
    #   * `checkin_idempotency` fuehrt laut eigenem Modell-Docstring bewusst keinen
    #     privaten Response-Cache, sondern nur einen Payload-Hash (Request-Identitaet).
    ("entitlement_assignments", "user_id"),
    ("checkin_idempotency", "user_id"),
]

#: Tabellen mit FK auf users.id, die dieser Seed nicht befuellt. Sie werden bewusst
#: klassifiziert statt ignoriert, damit `test_every_user_referencing_table_is_covered`
#: aussagekraeftig bleibt (eine neue, unklassifizierte Tabelle muss auffallen). Ueber
#: sie wird hier keine Mengenaussage gemacht -- nur die globale FK-Integritaet gilt.
MAY_BE_RETAINED = [
    # Kein Verlauf in diesem Seed: der Test sendet keine Copilot-Nachrichten.
    ("chat_messages", "author_user_id"),
    # Der Admin-Audit-Pfad wird von diesem Seed nicht ausgeloest.
    ("admin_audit_events", "actor_user_id"),
    ("admin_audit_events", "target_user_id"),
]


async def _switch(client, email: str) -> dict:
    await client.post("/v1/auth/logout")
    response = await client.post("/v1/auth/login", json={"email": email, "password": _PASSWORD})
    assert response.status_code == 200, response.text[:300]
    return {"x-csrf-token": client.cookies["numra_csrf"]}


async def _signup(client, sessionmaker, email: str) -> dict:
    async with sessionmaker() as db:
        await create_user(db, email=email, password_hash=hash_password(_PASSWORD))
        await db.commit()
    return await _switch(client, email)


async def _count_for(sessionmaker, table_name: str, column_name: str, user_id) -> int:
    table = Base.metadata.tables[table_name]
    column = table.c[column_name]
    async with sessionmaker() as db:
        return int(
            (
                await db.execute(select(func.count()).select_from(table).where(column == user_id))
            ).scalar_one()
        )


async def _seed_rich_account(client, sessionmaker) -> tuple[dict, str]:
    """Zwei synthetische Konten mit reichhaltigen Daten, wie das Produkt sie erzeugt."""
    owner = await _signup(client, sessionmaker, _DELETED_OWNER)
    invitation = (
        await client.post("/v1/connections/invitations", json={"method": "LINK"}, headers=owner)
    ).json()
    partner = await _signup(client, sessionmaker, _PARTNER)
    redeem = await client.post(
        "/v1/connections/invitations/redeem",
        json={"token": invitation["token"]},
        headers=partner,
    )
    assert redeem.status_code == 201, redeem.text[:300]
    workspace_id = redeem.json()["workspace_id"]

    owner = await _switch(client, _DELETED_OWNER)

    task = await client.post(
        f"/v1/workspaces/{workspace_id}/tasks",
        json={"task_type": "JOINT_SHARED", "title": "Gemeinsam wandern"},
        headers=owner,
    )
    assert task.status_code == 201, task.text[:300]
    # Kein expliziter Accept-Schritt: `JOINT_SHARED` legt die task_acceptances-Zeile
    # bereits beim Anlegen an (empirisch geprueft), und ein zweiter Aufruf ueber einen
    # anderen Nutzer ist hier nur eine zusaetzliche Fehlerquelle.

    roadmap = await client.post(
        f"/v1/workspaces/{workspace_id}/roadmaps",
        json={"roadmap_type": "14_DAY", "title": "Gemeinsamer Plan"},
        headers=owner,
    )
    assert roadmap.status_code == 201, roadmap.text[:300]

    person = await client.post(
        "/v1/people",
        json={
            "birth_first_names": "Anna",
            "birth_last_name": "Beispiel",
            "birth_date": "1990-03-14",
        },
        headers=owner,
    )
    assert person.status_code == 201, person.text[:300]
    reflection = await client.post(
        f"/v1/people/{person.json()['id']}/private-reflections",
        json={"entry_date": "2026-08-19", "content": "Ganz privat"},
        headers=owner,
    )
    assert reflection.status_code == 201, reflection.text[:300]
    shared = await client.post(
        f"/v1/private-reflections/{reflection.json()['id']}/share",
        json={"workspace_id": workspace_id},
        headers=owner,
    )
    assert shared.status_code == 201, shared.text[:300]

    for scope in ("RELATIONSHIP_SHARED", "RELATIONSHIP_PRIVATE"):
        thread = await client.post(
            f"/v1/workspaces/{workspace_id}/copilot/threads",
            json={"scope": scope},
            headers=owner,
        )
        assert thread.status_code in (200, 201), thread.text[:300]

    owner = await _switch(client, _DELETED_OWNER)
    owner_id = await _owner_id(sessionmaker)
    await _seed_private_rows(sessionmaker, workspace_id=workspace_id, owner_id=owner_id)
    return owner, workspace_id


async def _owner_id(sessionmaker) -> object:
    async with sessionmaker() as db:
        return (await db.execute(select(User.id).where(User.email == _DELETED_OWNER))).scalar_one()


async def _seed_private_rows(sessionmaker, *, workspace_id, owner_id) -> None:
    """Befuellt JEDE Tabelle aus MUST_BE_EMPTY mit mindestens einer Zeile.

    Ohne diesen Schritt waeren die meisten MUST_BE_EMPTY-Assertions `0 == 0` -- sie
    wuerden auch dann gruen sein, wenn der Loeschpfad die Tabelle komplett ignoriert.
    Genau dieser Fehler ist beim Schreiben der Matrix aufgefallen (eine Mutationsprobe
    gegen `delete_private_content` blieb gruen), deshalb wird hier direkt ueber das
    ORM befuellt: der Vertrag lautet "gegeben die Zeile existiert, ist sie danach weg".
    """
    async with sessionmaker() as db:
        person_row = (
            await db.execute(
                select(PrivateReflection.person_id).where(PrivateReflection.user_id == owner_id)
            )
        ).scalar_one()
        # Eine Person allein legt keine Calculation an (die entsteht erst beim
        # Rechnen), also hier direkt eine Zeile -- die abhaengigen Tabellen brauchen sie.
        calculation = Calculation(
            person_id=person_row,
            calculation_version="1",
            schema_version="1",
            as_of_date=dt.date(2026, 8, 19),
            input_snapshot={},
            canonical_profile_json={},
            deterministic_hash="deadbeef",
        )
        db.add(calculation)
        await db.flush()
        thread = (
            await db.execute(
                select(ChatThread).where(ChatThread.owner_user_id == owner_id).limit(1)
            )
        ).scalar_one()

        db.add(PrivateNote(user_id=owner_id, person_id=person_row, title="N", content="privat"))
        db.add(PersonalTask(user_id=owner_id, person_id=person_row, title="Aufgabe"))
        db.add(
            PatternAnalysis(
                user_id=owner_id,
                person_id=person_row,
                evidence_policy_version=1,
                metric_key="m",
                correlation_target="t",
                correlation_target_value=1,
                result_json={},
            )
        )
        db.add(
            RelationshipComparison(
                user_id=owner_id,
                calculation_a_id=calculation.id,
                calculation_b_id=calculation.id,
                comparison_json={},
            )
        )
        report = Report(
            user_id=owner_id,
            calculation_id=calculation.id,
            report_type="QUICK",
            calculation_version="1",
            knowledge_version="1",
            prompt_version="1",
            profile_snapshot={},
            report_schema_version="1",
        )
        db.add(report)
        await db.flush()
        db.add(ReportJob(report_id=report.id, user_id=owner_id))
        db.add(Export(user_id=owner_id, report_id=report.id, export_type="PDF"))
        db.add(Session(user_id=owner_id, token_hash="deadbeef", expires_at=_expiry()))
        db.add(
            EmailVerificationToken(user_id=owner_id, token_hash="deadbeef", expires_at=_expiry())
        )
        db.add(PasswordResetToken(user_id=owner_id, token_hash="deadbeef", expires_at=_expiry()))
        db.add(
            EntitlementAssignment(
                user_id=owner_id,
                entitlement_set_id=(
                    await db.execute(select(Base.metadata.tables["entitlement_sets"].c.id).limit(1))
                ).scalar_one(),
            )
        )
        db.add(
            LifeTrackingEntry(
                user_id=owner_id,
                person_id=person_row,
                entry_date=dt.date(2026, 8, 19),
            )
        )
        dimension = CheckinDimension(
            workspace_id=workspace_id, template_version=1, semantic_key="s", label="L"
        )
        checkin = RelationshipCheckin(workspace_id=workspace_id, checkin_template_version=1)
        db.add(dimension)
        db.add(checkin)
        await db.flush()
        db.add(
            CheckinResponse(
                checkin_id=checkin.id,
                user_id=owner_id,
                dimension_id=dimension.id,
                semantic_key="s",
                value=3,
            )
        )
        db.add(
            CheckinIdempotency(
                workspace_id=workspace_id,
                user_id=owner_id,
                checkin_id=checkin.id,
                payload_hash="deadbeef",
                operation="CHECKIN_SUBMIT",
                key="k",
            )
        )
        db.add(
            ThreadContextSnapshot(
                thread_id=thread.id,
                requester_user_id=owner_id,
                scope="RELATIONSHIP_PRIVATE",
                context_version=1,
                context_blocks_json=[],
                consent_scopes_checked=[],
            )
        )
        db.add(
            AnalysisJob(
                workspace_id=workspace_id,
                requested_by_user_id=owner_id,
                analysis_type="RELATIONSHIP_ANALYSIS",
            )
        )
        await db.commit()


# ---------------------------------------------------------------------------
# Der Vertrag
# ---------------------------------------------------------------------------


async def test_every_user_referencing_table_is_covered_by_the_matrix() -> None:
    """Die Matrix darf nicht veralten: eine neue Tabelle mit FK auf users.id, die in
    keiner der beiden Listen steht, faellt hier auf statt still undokumentiert zu sein.
    """
    declared = (
        {name for name, _ in MUST_BE_EMPTY}
        | {name for name, _ in MUST_BE_RETAINED}
        | {name for name, _ in MAY_BE_RETAINED}
    )
    actual = set()
    for table in Base.metadata.sorted_tables:
        if table.name == "users":
            continue
        for column in table.columns:
            for fk in column.foreign_keys:
                if fk.target_fullname == "users.id":
                    actual.add(table.name)
    missing = sorted(actual - declared)
    assert not missing, (
        "Tabellen mit FK auf users.id fehlen in der Retention-Matrix "
        f"(MUST_BE_EMPTY oder MUST_BE_RETAINED ergaenzen): {missing}"
    )


async def test_private_content_is_gone_and_shared_history_retained(client, sessionmaker) -> None:
    owner_headers, _ = await _seed_rich_account(client, sessionmaker)
    owner_id = await _owner_id(sessionmaker)

    # Vorbedingung: der Seed hat wirklich Daten erzeugt (sonst prueft der Test nichts).
    assert await _count_for(sessionmaker, "people", "user_id", owner_id) == 1
    assert await _count_for(sessionmaker, "chat_threads", "owner_user_id", owner_id) >= 1
    # ... und JEDE MUST_BE_EMPTY-Tabelle ist befuellt. Damit kann keine der Assertions
    # weiter unten ein blosses 0 == 0 sein.
    unfilled = []
    for table_name, column_name in MUST_BE_EMPTY:
        if await _count_for(sessionmaker, table_name, column_name, owner_id) < 1:
            unfilled.append(f"{table_name}.{column_name}")
    assert not unfilled, (
        "diese Privat-Tabellen sind im Seed leer, ihre Loeschung waere also nicht "
        f"bewiesen (Fixture ergaenzen): {unfilled}"
    )

    deleted = await client.post(
        "/v1/account/delete-all", json={"password": _PASSWORD}, headers=owner_headers
    )
    assert deleted.status_code in (200, 204), deleted.text[:300]

    for table_name, column_name in MUST_BE_EMPTY:
        remaining = await _count_for(sessionmaker, table_name, column_name, owner_id)
        assert remaining == 0, (
            f"{table_name}.{column_name} enthaelt nach der Loeschung noch {remaining} "
            "Zeile(n) -- privater Inhalt muss entfernt werden (ADR-013)"
        )

    for table_name, column_name in MUST_BE_RETAINED:
        remaining = await _count_for(sessionmaker, table_name, column_name, owner_id)
        assert remaining >= 1, (
            f"{table_name}.{column_name} ist nach der Loeschung leer -- geteilte "
            "Historie muss erhalten bleiben (ADR-013)"
        )


async def test_retained_rows_are_marked_not_live(client, sessionmaker) -> None:
    """Erhalten heisst nicht "unveraendert funktionsfaehig": Verbindung, Mitgliedschaft
    und Einwilligungen muessen sichtbar beendet sein."""
    owner_headers, workspace_id = await _seed_rich_account(client, sessionmaker)
    owner_id = await _owner_id(sessionmaker)

    deleted = await client.post(
        "/v1/account/delete-all", json={"password": _PASSWORD}, headers=owner_headers
    )
    assert deleted.status_code in (200, 204), deleted.text[:300]

    async with sessionmaker() as db:
        connection = (
            (
                await db.execute(
                    select(UserConnection).where(
                        (UserConnection.user_a_id == owner_id)
                        | (UserConnection.user_b_id == owner_id)
                    )
                )
            )
            .scalars()
            .one()
        )
        assert connection.status == ConnectionStatus.DISSOLVED

        member = (
            (await db.execute(select(WorkspaceMember).where(WorkspaceMember.user_id == owner_id)))
            .scalars()
            .one()
        )
        assert member.status == WorkspaceMemberStatus.REMOVED

        grants = (
            (await db.execute(select(ConsentGrant).where(ConsentGrant.grantor_user_id == owner_id)))
            .scalars()
            .all()
        )
        assert grants, "die Consent-Zeilen bleiben als Spur erhalten"
        assert all(grant.revoked_at is not None for grant in grants), (
            "jede Einwilligung des geloeschten Nutzers muss widerrufen sein (revoked_at "
            "gesetzt, Zeile bleibt fuer die Audit-Spur) -- ADR-013"
        )

        events = (
            (await db.execute(select(ConsentEvent).where(ConsentEvent.actor_user_id == owner_id)))
            .scalars()
            .all()
        )
        assert events, "die Audit-Spur bleibt erhalten"


async def test_tombstone_carries_no_pii(client, sessionmaker) -> None:
    """Die ueberlebende users-Zeile darf kein personenbezogenes Merkmal mehr tragen."""
    owner_headers, _ = await _seed_rich_account(client, sessionmaker)
    deleted = await client.post(
        "/v1/account/delete-all", json={"password": _PASSWORD}, headers=owner_headers
    )
    assert deleted.status_code in (200, 204), deleted.text[:300]

    async with sessionmaker() as db:
        tombstone = (
            (await db.execute(select(User).where(User.email.like("deleted+%")))).scalars().all()
        )
        # Genau eine Zeile, und sie traegt weder die alte Adresse noch das alte Geheimnis.
        assert len(tombstone) == 1, "genau ein ueberlebender Tombstone erwartet"
        row = tombstone[0]
        assert row.email != _DELETED_OWNER
        assert row.is_active is False
        assert row.deleted_at is not None
        assert not verify_password(row.password_hash, _PASSWORD), (
            "das alte Passwort darf auf dem Tombstone nicht mehr gelten"
        )
        # Das Opfer-Konto ist weg, das des Partners unberuehrt.
        partner = (
            await db.execute(select(User).where(User.email == _PARTNER))
        ).scalar_one_or_none()
        assert partner is not None, "das Partner-Konto darf nicht angetastet werden"
        assert partner.is_active is True
        assert partner.deleted_at is None


async def test_no_dangling_foreign_keys_anywhere_in_the_schema(client, sessionmaker) -> None:
    """Die systematische Haelfte des Nachweises.

    Eine vergessene Kindtabelle faellt nicht zwingend dadurch auf, dass eine *fremde*
    Zeile verschwindet -- sie faellt dadurch auf, dass ein ForeignKey ins Leere zeigt.
    Hier wird jeder Single-Column-FK des ganzen Schemas gegen den Elternbestand geprueft.
    """
    owner_headers, _ = await _seed_rich_account(client, sessionmaker)
    deleted = await client.post(
        "/v1/account/delete-all", json={"password": _PASSWORD}, headers=owner_headers
    )
    assert deleted.status_code in (200, 204), deleted.text[:300]

    checked = 0
    dangling: list[str] = []
    async with sessionmaker() as db:
        for table in Base.metadata.sorted_tables:
            for fk in table.foreign_keys:
                child = fk.parent
                parent = fk.column
                if parent.table is child.table:
                    continue  # Selbstreferenz: eigene Regel, hier nicht der Vertrag
                checked += 1
                orphans = (
                    await db.execute(
                        select(func.count())
                        .select_from(table)
                        .where(
                            child.is_not(None),
                            ~select(parent).where(parent == child).exists(),
                        )
                    )
                ).scalar_one()
                if int(orphans):
                    dangling.append(f"{table.name}.{child.name} -> {int(orphans)}")

    assert checked > 30, f"zu wenige FKs geprueft ({checked}) -- der Sweep greift nicht"
    assert not dangling, "verwaiste ForeignKeys nach der Kontoloeschung:\n" + "\n".join(dangling)
