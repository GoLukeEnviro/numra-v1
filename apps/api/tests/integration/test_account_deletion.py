"""PR-V2-10 -- Account-Löschung als Soft-Delete + PII-Scrub
(services/account_deletion_service.py, repositories/account.py).

Der Vertrag, den diese Datei absichert: privat = weg, geteilt = bleibt, und der
verbliebene Partner sieht ab jetzt ein Pseudonym statt der Original-E-Mail. Der
`users`-Row überlebt bewusst als getilgter Tombstone -- test_delete_all.py deckt die
Zeilen-für-Zeilen-Löschung der privaten Kindtabellen ab, hier steht die
Zwei-Parteien-Sicht.
"""

from __future__ import annotations

import pytest
from sqlalchemy import func, select

from numra_api.analysis_worker import run_one_cycle
from numra_api.auth.passwords import hash_password, verify_password
from numra_api.models import (
    ChatThread,
    ConsentGrant,
    PrivateReflection,
    RelationshipAnalysis,
    RelationshipRoadmap,
    RelationshipWorkspace,
    SharedReflection,
    User,
    UserConnection,
    WorkspaceMember,
    WorkspaceTask,
)
from numra_api.models.enums import (
    ConnectionStatus,
    ThreadScope,
    WorkspaceMemberStatus,
    WorkspaceStatus,
)
from numra_api.repositories.users import create_user

pytestmark = pytest.mark.integration

_PASSWORD = "password12345"


async def _signup(client, sessionmaker, email: str) -> dict:
    async with sessionmaker() as db:
        await create_user(db, email=email, password_hash=hash_password(_PASSWORD))
        await db.commit()
    return await _switch_user(client, email)


async def _switch_user(client, email: str) -> dict:
    await client.post("/v1/auth/logout")
    response = await client.post("/v1/auth/login", json={"email": email, "password": _PASSWORD})
    assert response.status_code == 200
    return {"x-csrf-token": client.cookies["numra_csrf"]}


async def _connect(client, sessionmaker, email_a: str, email_b: str) -> str:
    """Leaves the active session as user B (the redeemer)."""
    headers_a = await _signup(client, sessionmaker, email_a)
    invitation = (
        await client.post("/v1/connections/invitations", json={"method": "LINK"}, headers=headers_a)
    ).json()
    headers_b = await _signup(client, sessionmaker, email_b)
    redeem = await client.post(
        "/v1/connections/invitations/redeem",
        json={"token": invitation["token"]},
        headers=headers_b,
    )
    assert redeem.status_code == 201
    return redeem.json()["workspace_id"]


async def _delete_account(client, headers: dict, password: str = _PASSWORD):
    return await client.post("/v1/account/delete-all", json={"password": password}, headers=headers)


async def _count(sessionmaker, model) -> int:
    async with sessionmaker() as db:
        return int((await db.execute(select(func.count()).select_from(model))).scalar_one())


async def _seed_shared_and_private(client, sessionmaker, workspace_id: str, email_a: str) -> dict:
    """User A legt an: einen geteilten Task, eine geteilte Roadmap, eine geteilte
    Reflexion (aus einer privaten), einen SHARED- und einen PRIVATE-Copilot-Thread."""
    headers_a = await _switch_user(client, email_a)

    task = await client.post(
        f"/v1/workspaces/{workspace_id}/tasks",
        json={"task_type": "JOINT_SHARED", "title": "Gemeinsam wandern"},
        headers=headers_a,
    )
    assert task.status_code == 201
    roadmap = await client.post(
        f"/v1/workspaces/{workspace_id}/roadmaps",
        json={"roadmap_type": "14_DAY", "title": "Gemeinsamer Plan"},
        headers=headers_a,
    )
    assert roadmap.status_code == 201

    person = await client.post(
        "/v1/people",
        json={
            "birth_first_names": "Anna",
            "birth_last_name": "Beispiel",
            "birth_date": "1990-03-14",
        },
        headers=headers_a,
    )
    assert person.status_code == 201
    reflection = await client.post(
        f"/v1/people/{person.json()['id']}/private-reflections",
        json={"entry_date": "2026-08-19", "content": "Ganz privat"},
        headers=headers_a,
    )
    assert reflection.status_code == 201
    shared = await client.post(
        f"/v1/private-reflections/{reflection.json()['id']}/share",
        json={"workspace_id": workspace_id},
        headers=headers_a,
    )
    assert shared.status_code == 201

    for scope in ("RELATIONSHIP_SHARED", "RELATIONSHIP_PRIVATE"):
        thread = await client.post(
            f"/v1/workspaces/{workspace_id}/copilot/threads",
            json={"scope": scope},
            headers=headers_a,
        )
        assert thread.status_code in (200, 201)

    return {"task_id": task.json()["id"], "roadmap_id": roadmap.json()["id"]}


# ---------------------------------------------------------------------------
# Privat weg / geteilt bleibt
# ---------------------------------------------------------------------------


async def test_private_data_gone_shared_artefacts_retained(client, sessionmaker) -> None:
    workspace_id = await _connect(
        client, sessionmaker, "del-keep-a@example.com", "del-keep-b@example.com"
    )
    ids = await _seed_shared_and_private(
        client, sessionmaker, workspace_id, "del-keep-a@example.com"
    )

    headers_a = await _switch_user(client, "del-keep-a@example.com")
    assert (await _delete_account(client, headers_a)).status_code == 204

    # Privat: weg.
    assert await _count(sessionmaker, PrivateReflection) == 0
    async with sessionmaker() as db:
        private_threads = (
            await db.execute(
                select(func.count())
                .select_from(ChatThread)
                .where(ChatThread.scope == ThreadScope.RELATIONSHIP_PRIVATE)
            )
        ).scalar_one()
        assert private_threads == 0

    # Geteilt: bleibt -- als Row und für den Partner lesbar.
    assert await _count(sessionmaker, WorkspaceTask) == 1
    assert await _count(sessionmaker, RelationshipRoadmap) == 1
    assert await _count(sessionmaker, SharedReflection) == 1
    async with sessionmaker() as db:
        shared_threads = (
            await db.execute(
                select(func.count())
                .select_from(ChatThread)
                .where(ChatThread.scope == ThreadScope.RELATIONSHIP_SHARED)
            )
        ).scalar_one()
        assert shared_threads == 1

    headers_b = await _switch_user(client, "del-keep-b@example.com")
    task = await client.get(
        f"/v1/workspaces/{workspace_id}/tasks/{ids['task_id']}", headers=headers_b
    )
    assert task.status_code == 200
    assert task.json()["title"] == "Gemeinsam wandern"
    roadmap = await client.get(
        f"/v1/workspaces/{workspace_id}/roadmaps/{ids['roadmap_id']}", headers=headers_b
    )
    assert roadmap.status_code == 200
    reflections = await client.get(
        f"/v1/workspaces/{workspace_id}/shared-reflections", headers=headers_b
    )
    assert reflections.status_code == 200
    assert len(reflections.json()) == 1


# ---------------------------------------------------------------------------
# Pseudonymisierung
# ---------------------------------------------------------------------------


async def test_partner_sees_pseudonym_instead_of_original_email(client, sessionmaker) -> None:
    email_a = "del-pseudo-a@example.com"
    workspace_id = await _connect(client, sessionmaker, email_a, "del-pseudo-b@example.com")

    headers_b = await _switch_user(client, "del-pseudo-b@example.com")
    before = await client.get(f"/v1/workspaces/{workspace_id}", headers=headers_b)
    assert before.status_code == 200
    assert email_a in {m["display_name"] for m in before.json()["dual_profile"]}

    headers_a = await _switch_user(client, email_a)
    assert (await _delete_account(client, headers_a)).status_code == 204

    headers_b = await _switch_user(client, "del-pseudo-b@example.com")
    after = await client.get(f"/v1/workspaces/{workspace_id}", headers=headers_b)
    assert after.status_code == 200
    names = {m["display_name"] for m in after.json()["dual_profile"]}
    assert "Ehemaliges Mitglied" in names
    assert email_a not in names
    assert not any("@example.com" in name and name != "del-pseudo-b@example.com" for name in names)

    async with sessionmaker() as db:
        member = (
            await db.execute(
                select(WorkspaceMember).where(
                    WorkspaceMember.workspace_id == workspace_id,
                    WorkspaceMember.status == WorkspaceMemberStatus.REMOVED,
                )
            )
        ).scalar_one()
        assert member is not None


# ---------------------------------------------------------------------------
# Login / Re-Signup
# ---------------------------------------------------------------------------


async def test_deleted_user_cannot_log_in_but_email_is_free_again(client, sessionmaker) -> None:
    email = "del-login@example.com"
    headers = await _signup(client, sessionmaker, email)
    assert (await _delete_account(client, headers)).status_code == 204

    await client.post("/v1/auth/logout")
    login = await client.post("/v1/auth/login", json={"email": email, "password": _PASSWORD})
    assert login.status_code == 401
    assert login.json()["code"] == "INVALID_CREDENTIALS"

    # Die Original-Adresse ist wieder frei: der Unique-Index auf `users.email` lässt
    # eine Neuanlage zu (der Tombstone trägt die Wegwerf-Adresse), und der neue Account
    # kann sich mit einem neuen Passwort anmelden. Bewusst über `create_user` statt
    # `POST /v1/auth/register` -- `allow_self_signup` ist Deployment-Policy und nicht
    # Gegenstand dieses PRs.
    async with sessionmaker() as db:
        recreated = await create_user(db, email=email, password_hash=hash_password("brandnew123"))
        await db.commit()
        recreated_id = recreated.id

    relogin = await client.post("/v1/auth/login", json={"email": email, "password": "brandnew123"})
    assert relogin.status_code == 200
    assert relogin.json()["id"] == str(recreated_id)

    async with sessionmaker() as db:
        rows = (await db.execute(select(User))).scalars().all()
    assert len(rows) == 2
    assert sum(1 for r in rows if r.email == email) == 1


# ---------------------------------------------------------------------------
# Kein verwaistes PII
# ---------------------------------------------------------------------------


async def test_no_orphaned_pii_on_the_tombstone_row(client, sessionmaker) -> None:
    email = "del-scrub@example.com"
    headers = await _signup(client, sessionmaker, email)
    assert (await _delete_account(client, headers)).status_code == 204

    async with sessionmaker() as db:
        user = (await db.execute(select(User))).scalars().one()
        assert user.email != email
        assert user.email.startswith("deleted+")
        assert user.email.endswith("@deleted.avenyth.invalid")
        assert user.display_name_override == "Ehemaliges Mitglied"
        assert user.deleted_at is not None
        assert user.is_active is False
        # Das Hash wurde durch ein zufälliges Geheimnis ersetzt, nicht geleert oder
        # konstant gesetzt -- das alte Passwort darf nirgends mehr verifizieren.
        assert user.password_hash
        assert verify_password(user.password_hash, _PASSWORD) is False


# ---------------------------------------------------------------------------
# Consent-Schließung
# ---------------------------------------------------------------------------


async def test_consent_is_revoked_symmetrically_on_deletion(client, sessionmaker) -> None:
    """Beide Richtungen werden revoked -- der Partner kann im gemeinsamen Thread nichts
    Neues mehr erzeugen, weil die Grounding-Freigabe des Gelöschten weg ist."""
    workspace_id = await _connect(
        client, sessionmaker, "del-consent-a@example.com", "del-consent-b@example.com"
    )
    headers_b = await _switch_user(client, "del-consent-b@example.com")
    thread = await client.post(
        f"/v1/workspaces/{workspace_id}/copilot/threads",
        json={"scope": "RELATIONSHIP_SHARED"},
        headers=headers_b,
    )
    assert thread.status_code in (200, 201)
    thread_id = thread.json()["id"]

    headers_a = await _switch_user(client, "del-consent-a@example.com")
    assert (await _delete_account(client, headers_a)).status_code == 204

    async with sessionmaker() as db:
        grants = (
            (
                await db.execute(
                    select(ConsentGrant).where(ConsentGrant.workspace_id == workspace_id)
                )
            )
            .scalars()
            .all()
        )
        assert len(grants) == 6
        assert all(g.revoked_at is not None for g in grants)

    headers_b = await _switch_user(client, "del-consent-b@example.com")
    post = await client.post(
        f"/v1/workspaces/{workspace_id}/copilot/threads/{thread_id}/messages",
        json={"content": "Bist du noch da?"},
        headers=headers_b,
    )
    # Account-Löschung von A dissolvt jetzt Workspace UND Connection (Finding 1,
    # spiegelt `dissolve_own_connection`) -- `assert_workspace_active_by_id` greift
    # als 409 VOR dem Consent-Check, exakt wie beim regulären Dissolve
    # (test_dissolution.py::test_no_new_copilot_message_after_dissolve).
    assert post.status_code == 409
    assert post.json()["code"] == "WORKSPACE_DISSOLVED"

    # Lesen bleibt für den Partner offen.
    read = await client.get(
        f"/v1/workspaces/{workspace_id}/copilot/threads/{thread_id}/messages", headers=headers_b
    )
    assert read.status_code == 200


# ---------------------------------------------------------------------------
# Geteilte Analyse bleibt lesbar nach Account-Löschung
# ---------------------------------------------------------------------------


async def _create_self_person_with_calculation(client, headers: dict, payload: dict) -> str:
    """Same shape as test_relationship_analysis.py's `_create_self_person`, but returns
    the new Calculation's id -- needed here to tell apart `calculation_a_id` vs
    `calculation_b_id` on the resulting `RelationshipAnalysis` row."""
    response = await client.post("/v1/people", json=payload, headers=headers)
    assert response.status_code == 201
    person_id = response.json()["id"]
    calc = await client.post(
        f"/v1/people/{person_id}/calculations",
        json={"as_of_date": "2026-08-19"},
        headers=headers,
    )
    assert calc.status_code == 201
    return calc.json()["id"]


async def test_relationship_analysis_stays_readable_for_partner_after_deletion(
    client, sessionmaker, lukas_payload, llm
) -> None:
    """specs/v2/dissolution-policy.md "What is retained read-only": eine bereits
    generierte `RelationshipAnalysis` bleibt für BEIDE ehemaligen Teilnehmer lesbar,
    auch nachdem einer seinen Account (und damit seine `Calculation`) gelöscht hat --
    die Zeile selbst überlebt (SET NULL statt CASCADE), `result_json` ist unverändert."""
    email_a = "del-analysis-a@example.com"
    email_b = "del-analysis-b@example.com"
    workspace_id = await _connect(client, sessionmaker, email_a, email_b)

    payload_b = {**lukas_payload, "birth_date": "1990-03-14"}  # Life Path 9
    calc_id_b = await _create_self_person_with_calculation(
        client, await _switch_user(client, email_b), payload_b
    )

    headers_a = await _switch_user(client, email_a)
    payload_a = {
        **lukas_payload,
        "birth_first_names": "Partner",
        "birth_last_name": "Eins",
        "birth_date": "1988-07-22",  # Life Path 1
    }
    calc_id_a = await _create_self_person_with_calculation(client, headers_a, payload_a)

    patch = await client.patch(
        f"/v1/workspaces/{workspace_id}", json={"relationship_type": "PARTNER"}, headers=headers_a
    )
    assert patch.status_code == 200

    create = await client.post(
        f"/v1/workspaces/{workspace_id}/relationship-analysis", json={}, headers=headers_a
    )
    assert create.status_code == 201
    analysis_id = create.json()["id"]

    claimed = await run_one_cycle(sessionmaker, llm=llm)
    assert claimed is True

    get_before = await client.get(
        f"/v1/workspaces/{workspace_id}/relationship-analysis/{analysis_id}", headers=headers_a
    )
    assert get_before.status_code == 200
    assert get_before.json()["status"] == "COMPLETE"
    result_before = get_before.json()["result"]
    assert result_before is not None

    async with sessionmaker() as db:
        analysis = await db.get(RelationshipAnalysis, analysis_id)
        assert analysis is not None
        # A's Calculation kann in `calculation_a_id` oder `calculation_b_id` gelandet
        # sein -- welches Feld hier NULL werden muss, ist ordnungsabhängig, nicht fix.
        a_field = (
            "calculation_a_id"
            if str(analysis.calculation_a_id) == calc_id_a
            else "calculation_b_id"
        )
        assert str(getattr(analysis, a_field)) == calc_id_a
        b_field = "calculation_b_id" if a_field == "calculation_a_id" else "calculation_a_id"
        assert str(getattr(analysis, b_field)) == calc_id_b

    headers_a = await _switch_user(client, email_a)
    assert (await _delete_account(client, headers_a)).status_code == 204

    async with sessionmaker() as db:
        analysis = await db.get(RelationshipAnalysis, analysis_id)
        assert analysis is not None
        assert getattr(analysis, a_field) is None
        assert str(getattr(analysis, b_field)) == calc_id_b
        assert analysis.result_json == result_before

    headers_b = await _switch_user(client, email_b)
    get_after = await client.get(
        f"/v1/workspaces/{workspace_id}/relationship-analysis/{analysis_id}", headers=headers_b
    )
    assert get_after.status_code == 200
    assert get_after.json()["status"] == "COMPLETE"
    assert get_after.json()["result"] == result_before


# ---------------------------------------------------------------------------
# Regression-Guard
# ---------------------------------------------------------------------------


async def test_wrong_password_deletes_nothing(client, sessionmaker) -> None:
    email = "del-wrongpw@example.com"
    headers = await _signup(client, sessionmaker, email)
    person = await client.post(
        "/v1/people",
        json={"birth_first_names": "Bleibt", "birth_last_name": "Da", "birth_date": "1990-03-14"},
        headers=headers,
    )
    assert person.status_code == 201

    response = await _delete_account(client, headers, password="totally-wrong")
    assert response.status_code == 401
    assert response.json()["code"] == "INVALID_CREDENTIALS"

    async with sessionmaker() as db:
        user = (await db.execute(select(User).where(User.email == email))).scalars().one()
        assert user.deleted_at is None
        assert user.is_active is True
        assert user.display_name_override is None

    me = await client.get("/v1/auth/me", headers=headers)
    assert me.status_code == 200
    people = await client.get("/v1/people", headers=headers)
    assert people.status_code == 200
    assert len(people.json()) == 1


# ---------------------------------------------------------------------------
# Finding 1 (CRITICAL) -- Account-Löschung disabled future shared operations
# ---------------------------------------------------------------------------


async def test_workspace_and_connection_are_dissolved_on_deletion(client, sessionmaker) -> None:
    """Direkte ORM-Query, kein API-Roundtrip-Vertrauen: `RelationshipWorkspace.status`
    UND `UserConnection.status` müssen nach A's Löschung DISSOLVED sein -- genau der
    Zustand, den ein regulärer `dissolve_own_connection`-Aufruf hinterlässt."""
    workspace_id = await _connect(
        client, sessionmaker, "del-dissolve-a@example.com", "del-dissolve-b@example.com"
    )
    headers_a = await _switch_user(client, "del-dissolve-a@example.com")
    assert (await _delete_account(client, headers_a)).status_code == 204

    async with sessionmaker() as db:
        workspace = (
            await db.execute(
                select(RelationshipWorkspace).where(RelationshipWorkspace.id == workspace_id)
            )
        ).scalar_one()
        assert workspace.status == WorkspaceStatus.DISSOLVED
        assert workspace.dissolved_at is not None

        connection = (
            await db.execute(
                select(UserConnection).where(UserConnection.id == workspace.connection_id)
            )
        ).scalar_one()
        assert connection.status == ConnectionStatus.DISSOLVED
        assert connection.dissolved_at is not None


async def test_no_new_shared_writes_in_workspace_after_deletion(client, sessionmaker) -> None:
    """B darf im ehemals geteilten Workspace nach A's Löschung keinen neuen
    JOINT_SHARED-Task, keine neue Roadmap und keine neue Check-in-Runde mehr anlegen --
    409 WORKSPACE_DISSOLVED, keine neue Row persistiert (specs/v2/dissolution-policy.md
    "Future shared operations: DISABLED")."""
    workspace_id = await _connect(
        client, sessionmaker, "del-noshare-a@example.com", "del-noshare-b@example.com"
    )
    headers_b = await _switch_user(client, "del-noshare-b@example.com")
    template = await client.get(
        f"/v1/workspaces/{workspace_id}/checkin-template", headers=headers_b
    )
    assert template.status_code == 200
    checkin_responses = [
        {"dimension_id": dimension["id"], "value": 7} for dimension in template.json()["dimensions"]
    ]

    headers_a = await _switch_user(client, "del-noshare-a@example.com")
    assert (await _delete_account(client, headers_a)).status_code == 204

    headers_b = await _switch_user(client, "del-noshare-b@example.com")
    task = await client.post(
        f"/v1/workspaces/{workspace_id}/tasks",
        json={"task_type": "JOINT_SHARED", "title": "Nach der Löschung"},
        headers=headers_b,
    )
    assert task.status_code == 409
    assert task.json()["code"] == "WORKSPACE_DISSOLVED"

    roadmap = await client.post(
        f"/v1/workspaces/{workspace_id}/roadmaps",
        json={"roadmap_type": "14_DAY", "title": "Nach der Löschung"},
        headers=headers_b,
    )
    assert roadmap.status_code == 409
    assert roadmap.json()["code"] == "WORKSPACE_DISSOLVED"

    checkin = await client.post(
        f"/v1/workspaces/{workspace_id}/checkins",
        json={"responses": checkin_responses},
        headers=headers_b,
    )
    assert checkin.status_code == 409
    assert checkin.json()["code"] == "WORKSPACE_DISSOLVED"

    assert await _count(sessionmaker, WorkspaceTask) == 0
    assert await _count(sessionmaker, RelationshipRoadmap) == 0


# ---------------------------------------------------------------------------
# Finding 2 (HIGH) -- _other_member_user_id filtert nicht nach ACTIVE
# ---------------------------------------------------------------------------


async def test_other_member_user_id_never_resolves_a_removed_ghost(client, sessionmaker) -> None:
    """Negativ: nach A's Löschung findet `consent_service._other_member_user_id` kein
    aktives Gegenüber mehr -- 404 NOT_FOUND, kein Grant gegen den Ghost-User A."""
    workspace_id = await _connect(
        client, sessionmaker, "del-ghost-a@example.com", "del-ghost-b@example.com"
    )
    headers_a = await _switch_user(client, "del-ghost-a@example.com")
    assert (await _delete_account(client, headers_a)).status_code == 204

    headers_b = await _switch_user(client, "del-ghost-b@example.com")
    grant = await client.post(
        f"/v1/workspaces/{workspace_id}/consent/grant",
        json={"scope": "CORE_NUMEROLOGY"},
        headers=headers_b,
    )
    assert grant.status_code == 404
    assert grant.json()["code"] == "NOT_FOUND"


async def test_other_member_user_id_still_resolves_remaining_active_workspace(
    client, sessionmaker
) -> None:
    """Positiv: B hat zwei Workspaces (mit A und mit C). Nachdem A seinen Account
    löscht, bleibt die Auflösung im B-C-Workspace unverändert korrekt -- die
    ACTIVE-Filterung darf ein noch intaktes Gegenüber nicht fälschlich verwerfen."""
    workspace_ab = await _connect(
        client, sessionmaker, "del-multi-a@example.com", "del-multi-b@example.com"
    )

    # C verbindet sich anschließend mit dem bereits existierenden B -- `_connect`
    # signupt beide Seiten neu, daher hier manuell (B existiert schon aus der
    # ersten Connection oben).
    headers_c = await _signup(client, sessionmaker, "del-multi-c@example.com")
    invitation_c = (
        await client.post("/v1/connections/invitations", json={"method": "LINK"}, headers=headers_c)
    ).json()
    headers_b = await _switch_user(client, "del-multi-b@example.com")
    redeem = await client.post(
        "/v1/connections/invitations/redeem",
        json={"token": invitation_c["token"]},
        headers=headers_b,
    )
    assert redeem.status_code == 201
    workspace_cb = redeem.json()["workspace_id"]

    headers_a = await _switch_user(client, "del-multi-a@example.com")
    assert (await _delete_account(client, headers_a)).status_code == 204

    headers_b = await _switch_user(client, "del-multi-b@example.com")
    grant = await client.post(
        f"/v1/workspaces/{workspace_cb}/consent/grant",
        json={"scope": "CORE_NUMEROLOGY"},
        headers=headers_b,
    )
    assert grant.status_code == 201

    ghost_grant = await client.post(
        f"/v1/workspaces/{workspace_ab}/consent/grant",
        json={"scope": "CORE_NUMEROLOGY"},
        headers=headers_b,
    )
    assert ghost_grant.status_code == 404
    assert ghost_grant.json()["code"] == "NOT_FOUND"
