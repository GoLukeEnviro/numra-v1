"""PWA-07 (#125) -- Lese-Projektionen fuer den Kontodatenexport.

Jede Abfrage in diesem Modul ist eine *Projektion*: sie waehlt genau die Spalten, die
das Export-Format dokumentiert, und sonst nichts. Das ist Absicht -- `password_hash`,
`token_hash`, `file_ref`, `idempotency_key` und die Context-Block-Snapshots des Copilot
werden nicht nachtraeglich aus einer vollen Zeile herausgefiltert, sie werden gar nicht
erst gelesen. Ein Feld kann damit nur im Export landen, wenn es hier namentlich steht.

Die zweite Zusage dieses Moduls ist die Eigentumsgrenze: `user_id` wird *nicht* als
Nachfilterung auf ein breites Ergebnis angewendet, sondern ist Teil jeder `WHERE`-Klausel
bzw. der `IN`-Liste, die aus den eigenen Zeilen (`workspaces`, `reports`, `chat_threads`)
abgeleitet wurde. Einfuegen ist ausgeschlossen, weil es hier ausschliesslich `SELECT`s
gibt.

Partnerbezug: eine "Verbindung", ein "Workspace" oder eine "geteilte Reflexion" traegt
notwendigerweise einen zweiten Menschen. Der Export nennt ihn ueber seinen
Produkt-Anzeigenamen (`person_display_name` bzw. `display_name_override`) -- nie ueber
`email` und nie ueber `users.id`. Damit bleibt die Zusage aus
`specs/v2/privacy-spec.md` (ein Konto sieht kein privates Konto eines anderen) auch im
Export wahr, waehrend die gemeinsame Historie vollstaendig bleibt.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from numra_api.models import (
    AnalysisJob,
    Calculation,
    ChatMessage,
    ChatThread,
    CheckinAnalysis,
    CheckinResponse,
    ConnectionInvitation,
    ConsentEvent,
    ConsentGrant,
    CustomMetricDefinition,
    EntitlementAssignment,
    EntitlementSet,
    Export,
    LifeTrackingEntry,
    LifeTrackingMetricValue,
    NameIdentity,
    PatternAnalysis,
    Person,
    PersonalTask,
    PrivateNote,
    PrivateReflection,
    RelationshipAnalysis,
    RelationshipCheckin,
    RelationshipComparison,
    RelationshipRoadmap,
    RelationshipWorkspace,
    Report,
    ReportJob,
    RoadmapMilestone,
    ShadowDynamicsAnalysis,
    SharedReflection,
    TaskAcceptance,
    User,
    UserConnection,
    WorkspaceMember,
    WorkspaceTask,
)
from numra_api.models.enums import ThreadScope
from numra_api.repositories.entitlements import DEFAULT_ENTITLEMENT_SET_KEY

#: Namen, unter denen der Export andere Menschen nennt, wenn kein Anzeigename
#: aufloesbar ist. Bewusst *keine* E-Mail und keine UUID -- siehe Modul-Docstring.
PARTNER_PLACEHOLDER = "Verbundene Person"


def _display_name(person: Person | None, user: User | None) -> str:
    """Spiegelt die Anzeigenamen-Aufloesung des Produkts
    (`services/relationship_workspace_service.py`): zuerst das sichtbare SELF-Profil,
    dann `display_name_override` (bei geloeschten Konten "Ehemaliges Mitglied"), dann
    der Platzhalter -- nie die E-Mail."""
    if person is not None:
        parts = person.preferred_name or person.birth_first_names
        if parts:
            return " ".join(part for part in (parts, person.birth_last_name) if part)
    if user is not None and user.display_name_override:
        return user.display_name_override
    return PARTNER_PLACEHOLDER


async def load_entitlements(db: AsyncSession, *, user_id: uuid.UUID) -> dict[str, Any]:
    """Der effektive `EntitlementSet` des Kontos (`GET /v1/me/entitlements`-Semantik),
    ohne die Zeilen-ID des Zuweisungsobjekts."""
    result = await db.execute(
        select(EntitlementSet)
        .join(EntitlementAssignment, EntitlementAssignment.entitlement_set_id == EntitlementSet.id)
        .where(EntitlementAssignment.user_id == user_id)
    )
    entitlement_set = result.scalar_one_or_none()

    assigned_at: Any = None
    if entitlement_set is None:
        result = await db.execute(
            select(EntitlementSet).where(EntitlementSet.key == DEFAULT_ENTITLEMENT_SET_KEY)
        )
        entitlement_set = result.scalar_one_or_none()
    else:
        result = await db.execute(
            select(EntitlementAssignment.assigned_at).where(
                EntitlementAssignment.user_id == user_id
            )
        )
        assigned_at = result.scalar_one_or_none()

    if entitlement_set is None:
        # Nur erreichbar, wenn die Seed-Migration fehlt -- dann ist ein leeres Objekt
        # die ehrliche Antwort statt eines geratenen Standardwerts.
        return {"set_key": None, "assigned_at": None, "features": {}}

    return {
        "set_key": entitlement_set.key,
        "assigned_at": assigned_at,
        "features": {
            "personal_workspace": entitlement_set.personal_workspace,
            "connections": entitlement_set.connections,
            "relationship_workspaces": entitlement_set.relationship_workspaces,
            "relationship_checkins": entitlement_set.relationship_checkins,
            "relationship_copilot": entitlement_set.relationship_copilot,
            "advanced_relationship_analysis": entitlement_set.advanced_relationship_analysis,
            "life_tracking": entitlement_set.life_tracking,
            "premium_reports": entitlement_set.premium_reports,
            "max_connections": entitlement_set.max_connections,
            "max_workspaces": entitlement_set.max_workspaces,
        },
    }


async def load_profiles(db: AsyncSession, *, user_id: uuid.UUID) -> list[dict[str, Any]]:
    """Alle eigenen Profile (SELF wie verwaltete) mit Namensidentitaeten und
    Calculation-Revisionen. `input_snapshot`/`canonical_profile_json` sind
    Produktausgaben der Engine ueber die eigenen Geburtsdaten -- sie gehoeren dem
    Konto und stehen deshalb vollstaendig drin."""
    people = (
        (
            await db.execute(
                select(Person).where(Person.user_id == user_id).order_by(Person.created_at)
            )
        )
        .scalars()
        .all()
    )
    if not people:
        return []
    person_ids = [person.id for person in people]

    identities: dict[uuid.UUID, list[dict[str, Any]]] = {person_id: [] for person_id in person_ids}
    rows = (
        await db.execute(
            select(
                NameIdentity.person_id,
                NameIdentity.kind,
                NameIdentity.first_names,
                NameIdentity.middle_names,
                NameIdentity.last_name,
                NameIdentity.valid_from,
                NameIdentity.valid_to,
                NameIdentity.created_at,
            )
            .where(NameIdentity.person_id.in_(person_ids))
            .order_by(NameIdentity.created_at)
        )
    ).mappings()
    for row in rows:
        identities[row["person_id"]].append(dict(row))

    calculations: dict[uuid.UUID, list[dict[str, Any]]] = {
        person_id: [] for person_id in person_ids
    }
    rows = (
        await db.execute(
            select(
                Calculation.person_id,
                Calculation.id,
                Calculation.calculation_version,
                Calculation.schema_version,
                Calculation.as_of_date,
                Calculation.deterministic_hash,
                Calculation.input_snapshot,
                Calculation.canonical_profile_json,
                Calculation.created_at,
            )
            .where(Calculation.person_id.in_(person_ids))
            .order_by(Calculation.created_at)
        )
    ).mappings()
    for row in rows:
        calculations[row["person_id"]].append(dict(row))

    profiles: list[dict[str, Any]] = []
    for person in people:
        profiles.append(
            {
                "id": person.id,
                "account_mode": person.person_account_mode,
                "birth_first_names": person.birth_first_names,
                "birth_middle_names": person.birth_middle_names,
                "birth_last_name": person.birth_last_name,
                "birth_date": person.birth_date,
                "birth_time": person.birth_time,
                "birth_place": person.birth_place,
                "current_first_names": person.current_first_names,
                "current_middle_names": person.current_middle_names,
                "current_last_name": person.current_last_name,
                "preferred_name": person.preferred_name,
                "created_at": person.created_at,
                "updated_at": person.updated_at,
                "name_identities": identities[person.id],
                "calculations": calculations[person.id],
            }
        )
    return profiles


async def load_personal_workspace(db: AsyncSession, *, user_id: uuid.UUID) -> dict[str, Any]:
    """PERSONAL_PRIVATE-Flaeche: eigene Reflexionen, Notizen, Aufgaben, Life-Tracking
    und die gespeicherten Evidenz-Snapshots."""
    reflections = [
        dict(row)
        for row in (
            await db.execute(
                select(
                    PrivateReflection.id,
                    PrivateReflection.person_id,
                    PrivateReflection.entry_date,
                    PrivateReflection.content,
                    PrivateReflection.created_at,
                    PrivateReflection.updated_at,
                )
                .where(PrivateReflection.user_id == user_id)
                .order_by(PrivateReflection.entry_date)
            )
        ).mappings()
    ]
    notes = [
        dict(row)
        for row in (
            await db.execute(
                select(
                    PrivateNote.id,
                    PrivateNote.person_id,
                    PrivateNote.title,
                    PrivateNote.content,
                    PrivateNote.created_at,
                    PrivateNote.updated_at,
                )
                .where(PrivateNote.user_id == user_id)
                .order_by(PrivateNote.created_at)
            )
        ).mappings()
    ]
    tasks = [
        dict(row)
        for row in (
            await db.execute(
                select(
                    PersonalTask.id,
                    PersonalTask.person_id,
                    PersonalTask.title,
                    PersonalTask.description,
                    PersonalTask.due_date,
                    PersonalTask.status,
                    PersonalTask.completed_at,
                    PersonalTask.created_at,
                    PersonalTask.updated_at,
                )
                .where(PersonalTask.user_id == user_id)
                .order_by(PersonalTask.created_at)
            )
        ).mappings()
    ]
    entries = [
        dict(row)
        for row in (
            await db.execute(
                select(
                    LifeTrackingEntry.id,
                    LifeTrackingEntry.person_id,
                    LifeTrackingEntry.entry_date,
                    LifeTrackingEntry.mood,
                    LifeTrackingEntry.energy,
                    LifeTrackingEntry.sleep,
                    LifeTrackingEntry.stress,
                    LifeTrackingEntry.focus,
                    LifeTrackingEntry.note,
                    LifeTrackingEntry.created_at,
                    LifeTrackingEntry.updated_at,
                )
                .where(LifeTrackingEntry.user_id == user_id)
                .order_by(LifeTrackingEntry.entry_date)
            )
        ).mappings()
    ]
    if entries:
        entry_ids = [entry["id"] for entry in entries]
        values: dict[uuid.UUID, list[dict[str, Any]]] = {entry_id: [] for entry_id in entry_ids}
        for row in (
            await db.execute(
                select(
                    LifeTrackingMetricValue.entry_id,
                    LifeTrackingMetricValue.metric_key,
                    LifeTrackingMetricValue.value,
                )
                .where(LifeTrackingMetricValue.entry_id.in_(entry_ids))
                .order_by(LifeTrackingMetricValue.metric_key)
            )
        ).mappings():
            values[row["entry_id"]].append({"metric_key": row["metric_key"], "value": row["value"]})
        for entry in entries:
            entry["custom_values"] = values[entry["id"]]

    custom_metrics = [
        dict(row)
        for row in (
            await db.execute(
                select(
                    CustomMetricDefinition.id,
                    CustomMetricDefinition.person_id,
                    CustomMetricDefinition.metric_key,
                    CustomMetricDefinition.label,
                    CustomMetricDefinition.scale_min,
                    CustomMetricDefinition.scale_max,
                    CustomMetricDefinition.active,
                    CustomMetricDefinition.retired_at,
                    CustomMetricDefinition.created_at,
                )
                .where(
                    CustomMetricDefinition.person_id.in_(
                        select(Person.id).where(Person.user_id == user_id)
                    )
                )
                .order_by(CustomMetricDefinition.created_at)
            )
        ).mappings()
    ]
    pattern_analyses = [
        dict(row)
        for row in (
            await db.execute(
                select(
                    PatternAnalysis.id,
                    PatternAnalysis.person_id,
                    PatternAnalysis.evidence_policy_version,
                    PatternAnalysis.metric_key,
                    PatternAnalysis.correlation_target,
                    PatternAnalysis.correlation_target_value,
                    PatternAnalysis.result_json,
                    PatternAnalysis.created_at,
                )
                .where(PatternAnalysis.user_id == user_id)
                .order_by(PatternAnalysis.created_at)
            )
        ).mappings()
    ]

    return {
        "private_reflections": reflections,
        "private_notes": notes,
        "personal_tasks": tasks,
        "life_tracking_entries": entries,
        "custom_metrics": custom_metrics,
        "pattern_analyses": pattern_analyses,
    }


async def load_reports(db: AsyncSession, *, user_id: uuid.UUID) -> dict[str, Any]:
    """Report-Inhalte, minimale Job-Metadaten (ohne Lease-/Backoff-Interna) und die
    PDF-Exportzeilen ohne `file_ref` (opaker Speicherpfad)."""
    reports = [
        dict(row)
        for row in (
            await db.execute(
                select(
                    Report.id,
                    Report.calculation_id,
                    Report.report_type,
                    Report.status,
                    Report.calculation_version,
                    Report.knowledge_version,
                    Report.prompt_version,
                    Report.report_schema_version,
                    Report.model_provider,
                    Report.model_name,
                    Report.content_json,
                    Report.generated_at,
                    Report.created_at,
                )
                .where(Report.user_id == user_id)
                .order_by(Report.created_at)
            )
        ).mappings()
    ]
    jobs = [
        dict(row)
        for row in (
            await db.execute(
                select(
                    ReportJob.id,
                    ReportJob.report_id,
                    ReportJob.status,
                    ReportJob.progress,
                    ReportJob.attempt_count,
                    ReportJob.error_code,
                    ReportJob.created_at,
                )
                .where(ReportJob.user_id == user_id)
                .order_by(ReportJob.created_at)
            )
        ).mappings()
    ]
    exports = [
        dict(row)
        for row in (
            await db.execute(
                select(
                    Export.id,
                    Export.report_id,
                    Export.export_type,
                    Export.status,
                    Export.file_size_bytes,
                    Export.error_code,
                    Export.created_at,
                )
                .where(Export.user_id == user_id)
                .order_by(Export.created_at)
            )
        ).mappings()
    ]
    return {"reports": reports, "report_jobs": jobs, "report_exports": exports}


async def _messages_for_threads(
    db: AsyncSession, *, thread_ids: Sequence[uuid.UUID], user_id: uuid.UUID
) -> dict[uuid.UUID, list[dict[str, Any]]]:
    """Nachrichten aller uebergebenen Threads -- ohne `context_snapshot_id`, ohne
    `prompt_version`/`knowledge_version`-Interna und ohne `author_user_id` (die
    Urheberschaft wird als `"self"`/`"counterpart"`/`"assistant"` ausgedrueckt, damit
    keine fremde Nutzer-UUID im Dokument steht). Die Kontextbloecke selbst
    (`thread_context_snapshots`) werden an keiner Stelle gelesen."""
    messages: dict[uuid.UUID, list[dict[str, Any]]] = {thread_id: [] for thread_id in thread_ids}
    if not thread_ids:
        return messages
    rows = (
        await db.execute(
            select(
                ChatMessage.thread_id,
                ChatMessage.id,
                ChatMessage.role,
                ChatMessage.status,
                ChatMessage.content,
                ChatMessage.basis_type,
                ChatMessage.author_user_id,
                ChatMessage.created_at,
            )
            .where(ChatMessage.thread_id.in_(thread_ids))
            .order_by(ChatMessage.created_at)
        )
    ).mappings()
    for row in rows:
        if row["role"] == "ASSISTANT":
            author = "assistant"
        else:
            author = "self" if row["author_user_id"] == user_id else "counterpart"
        messages[row["thread_id"]].append(
            {
                "id": row["id"],
                "role": row["role"],
                "status": row["status"],
                "content": row["content"],
                "basis_type": row["basis_type"],
                "author": author,
                "created_at": row["created_at"],
            }
        )
    return messages


async def load_personal_copilot(db: AsyncSession, *, user_id: uuid.UUID) -> dict[str, Any]:
    """Nur `PERSONAL_PRIVATE`-Threads des Kontos. Threads eines geteilten Workspace
    stehen beim jeweiligen Workspace (siehe `load_workspaces`)."""
    threads = (
        (
            await db.execute(
                select(ChatThread)
                .where(
                    ChatThread.owner_user_id == user_id,
                    ChatThread.scope == ThreadScope.PERSONAL_PRIVATE,
                )
                .order_by(ChatThread.created_at)
            )
        )
        .scalars()
        .all()
    )
    messages = await _messages_for_threads(
        db, thread_ids=[thread.id for thread in threads], user_id=user_id
    )
    return {
        "threads": [
            {
                "id": thread.id,
                "scope": thread.scope,
                "context_version": thread.context_version,
                "created_at": thread.created_at,
                "archived_at": thread.archived_at,
                "messages": messages[thread.id],
            }
            for thread in threads
        ]
    }


async def load_standalone_relationships(db: AsyncSession, *, user_id: uuid.UUID) -> dict[str, Any]:
    """Die V1-Vergleichsobjekte (`relationships`), die ausgehenden Einladungen und die
    bestaetigten Verbindungen -- letztere mit dem Anzeigenamen der Gegenseite statt
    deren E-Mail."""
    comparisons = [
        dict(row)
        for row in (
            await db.execute(
                select(
                    RelationshipComparison.id,
                    RelationshipComparison.calculation_a_id,
                    RelationshipComparison.calculation_b_id,
                    RelationshipComparison.comparison_json,
                    RelationshipComparison.insights_json,
                    RelationshipComparison.created_at,
                )
                .where(RelationshipComparison.user_id == user_id)
                .order_by(RelationshipComparison.created_at)
            )
        ).mappings()
    ]

    invitations = [
        dict(row)
        for row in (
            await db.execute(
                select(
                    ConnectionInvitation.id,
                    ConnectionInvitation.method,
                    ConnectionInvitation.state,
                    ConnectionInvitation.expires_at,
                    ConnectionInvitation.created_at,
                    ConnectionInvitation.redeemed_at,
                    ConnectionInvitation.revoked_at,
                )
                .where(ConnectionInvitation.inviter_user_id == user_id)
                .order_by(ConnectionInvitation.created_at)
            )
        ).mappings()
    ]

    connections = (
        (
            await db.execute(
                select(UserConnection)
                .where(
                    (UserConnection.user_a_id == user_id) | (UserConnection.user_b_id == user_id)
                )
                .order_by(UserConnection.created_at)
            )
        )
        .scalars()
        .all()
    )
    partner_ids = [
        connection.user_b_id if connection.user_a_id == user_id else connection.user_a_id
        for connection in connections
    ]
    names = await _display_names_for_users(db, user_ids=partner_ids)

    return {
        "comparisons": comparisons,
        "invitations": invitations,
        "connections": [
            {
                "id": connection.id,
                "status": connection.status,
                "created_at": connection.created_at,
                "dissolved_at": connection.dissolved_at,
                "counterpart_display_name": names.get(partner_id, PARTNER_PLACEHOLDER),
            }
            for connection, partner_id in zip(connections, partner_ids, strict=True)
        ],
    }


async def _display_names_for_users(
    db: AsyncSession, *, user_ids: Sequence[uuid.UUID]
) -> dict[uuid.UUID, str]:
    """Anzeigename je fremder `users.id` -- aus dem sichtbaren SELF-Profil bzw.
    `display_name_override`. Eine E-Mail wird hier bewusst nicht als Rueckfall
    verwendet (anders als in der UI, die den Namen erst bei fehlender Freigabe
    ausblendet): der Export soll fremde Adressen gar nicht erst enthalten."""
    unique_ids = [user_id for user_id in dict.fromkeys(user_ids) if user_id is not None]
    if not unique_ids:
        return {}
    persons = (
        (
            await db.execute(
                select(Person).where(
                    Person.user_id.in_(unique_ids),
                    Person.person_account_mode == "SELF",
                )
            )
        )
        .scalars()
        .all()
    )
    users = (await db.execute(select(User).where(User.id.in_(unique_ids)))).scalars().all()
    by_user = {user.id: user for user in users}
    person_by_user = {person.user_id: person for person in persons}
    return {
        user_id: _display_name(person_by_user.get(user_id), by_user.get(user_id))
        for user_id in unique_ids
    }


async def load_workspaces(db: AsyncSession, *, user_id: uuid.UUID) -> list[dict[str, Any]]:
    """Alle geteilten Workspaces, in denen das Konto Mitglied ist -- mit den
    Artefakten, die das Produkt beiden Mitgliedern zeigt.

    Zwei Dinge sind hier bewusst *nicht* enthalten: die rohen Check-in-Antworten der
    Gegenseite (`specs/v2/checkin-spec.md` Section 19: SUBMITTER_ONLY -- nur die
    eigenen Zeilen werden gelesen) und die privaten Copilot-Threads der Gegenseite
    (`RELATIONSHIP_PRIVATE` wird auf `owner_user_id = user_id` gefiltert)."""
    memberships = (
        (await db.execute(select(WorkspaceMember).where(WorkspaceMember.user_id == user_id)))
        .scalars()
        .all()
    )
    workspace_ids = [member.workspace_id for member in memberships]
    if not workspace_ids:
        return []

    workspaces = (
        (
            await db.execute(
                select(RelationshipWorkspace)
                .where(RelationshipWorkspace.id.in_(workspace_ids))
                .order_by(RelationshipWorkspace.created_at)
            )
        )
        .scalars()
        .all()
    )

    all_members = (
        (
            await db.execute(
                select(WorkspaceMember).where(WorkspaceMember.workspace_id.in_(workspace_ids))
            )
        )
        .scalars()
        .all()
    )
    names = await _display_names_for_users(db, user_ids=[member.user_id for member in all_members])
    members_by_workspace: dict[uuid.UUID, list[dict[str, Any]]] = {
        workspace_id: [] for workspace_id in workspace_ids
    }
    for member in all_members:
        members_by_workspace[member.workspace_id].append(
            {
                "display_name": names.get(member.user_id, PARTNER_PLACEHOLDER),
                "role": "self" if member.user_id == user_id else "counterpart",
                "status": member.status,
                "joined_at": member.joined_at,
            }
        )

    grants = [
        dict(row)
        for row in (
            await db.execute(
                select(
                    ConsentGrant.workspace_id,
                    ConsentGrant.scope,
                    ConsentGrant.version,
                    ConsentGrant.grantor_user_id,
                    ConsentGrant.grantee_user_id,
                    ConsentGrant.granted_at,
                    ConsentGrant.revoked_at,
                )
                .where(
                    ConsentGrant.workspace_id.in_(workspace_ids),
                    (ConsentGrant.grantor_user_id == user_id)
                    | (ConsentGrant.grantee_user_id == user_id),
                )
                .order_by(ConsentGrant.granted_at)
            )
        ).mappings()
    ]
    grants_by_workspace: dict[uuid.UUID, list[dict[str, Any]]] = {
        workspace_id: [] for workspace_id in workspace_ids
    }
    for grant in grants:
        grants_by_workspace[grant["workspace_id"]].append(
            {
                "direction": "granted_by_me"
                if grant["grantor_user_id"] == user_id
                else "granted_to_me",
                "scope": grant["scope"],
                "version": grant["version"],
                "counterpart_display_name": names.get(
                    grant["grantee_user_id"]
                    if grant["grantor_user_id"] == user_id
                    else grant["grantor_user_id"],
                    PARTNER_PLACEHOLDER,
                ),
                "granted_at": grant["granted_at"],
                "revoked_at": grant["revoked_at"],
            }
        )

    events = [
        dict(row)
        for row in (
            await db.execute(
                select(
                    ConsentGrant.workspace_id,
                    ConsentEvent.event_type,
                    ConsentEvent.occurred_at,
                )
                .join(ConsentGrant, ConsentGrant.id == ConsentEvent.grant_id)
                .where(
                    ConsentGrant.workspace_id.in_(workspace_ids),
                    ConsentEvent.actor_user_id == user_id,
                )
                .order_by(ConsentEvent.occurred_at)
            )
        ).mappings()
    ]
    events_by_workspace: dict[uuid.UUID, list[dict[str, Any]]] = {
        workspace_id: [] for workspace_id in workspace_ids
    }
    for event in events:
        events_by_workspace[event["workspace_id"]].append(
            {"event_type": event["event_type"], "occurred_at": event["occurred_at"]}
        )

    tasks = (
        (
            await db.execute(
                select(WorkspaceTask)
                .where(WorkspaceTask.workspace_id.in_(workspace_ids))
                .order_by(WorkspaceTask.created_at)
            )
        )
        .scalars()
        .all()
    )
    acceptances: dict[uuid.UUID, list[dict[str, Any]]] = {task.id: [] for task in tasks}
    if tasks:
        for row in (
            await db.execute(
                select(
                    TaskAcceptance.task_id,
                    TaskAcceptance.event_type,
                    TaskAcceptance.actor_user_id,
                    TaskAcceptance.occurred_at,
                )
                .where(TaskAcceptance.task_id.in_([task.id for task in tasks]))
                .order_by(TaskAcceptance.occurred_at)
            )
        ).mappings():
            acceptances[row["task_id"]].append(
                {
                    "event_type": row["event_type"],
                    "actor": "self" if row["actor_user_id"] == user_id else "counterpart",
                    "occurred_at": row["occurred_at"],
                }
            )
    tasks_by_workspace: dict[uuid.UUID, list[dict[str, Any]]] = {
        workspace_id: [] for workspace_id in workspace_ids
    }
    for task in tasks:
        tasks_by_workspace[task.workspace_id].append(
            {
                "id": task.id,
                "task_type": task.task_type,
                "status": task.status,
                "title": task.title,
                "description": task.description,
                "due_date": task.due_date,
                "completed_at": task.completed_at,
                "created_at": task.created_at,
                "updated_at": task.updated_at,
                "proposer": None
                if task.proposer_user_id is None
                else ("self" if task.proposer_user_id == user_id else "counterpart"),
                "recipient": None
                if task.recipient_user_id is None
                else ("self" if task.recipient_user_id == user_id else "counterpart"),
                "events": acceptances[task.id],
            }
        )

    roadmaps = (
        (
            await db.execute(
                select(RelationshipRoadmap)
                .where(RelationshipRoadmap.workspace_id.in_(workspace_ids))
                .order_by(RelationshipRoadmap.created_at)
            )
        )
        .scalars()
        .all()
    )
    milestones: dict[uuid.UUID, list[dict[str, Any]]] = {roadmap.id: [] for roadmap in roadmaps}
    if roadmaps:
        for row in (
            await db.execute(
                select(
                    RoadmapMilestone.roadmap_id,
                    RoadmapMilestone.id,
                    RoadmapMilestone.milestone_type,
                    RoadmapMilestone.title,
                    RoadmapMilestone.description,
                    RoadmapMilestone.target_date,
                    RoadmapMilestone.sequence,
                    RoadmapMilestone.status,
                    RoadmapMilestone.completed_at,
                    RoadmapMilestone.created_at,
                )
                .where(RoadmapMilestone.roadmap_id.in_([roadmap.id for roadmap in roadmaps]))
                .order_by(RoadmapMilestone.sequence)
            )
        ).mappings():
            milestones[row["roadmap_id"]].append(dict(row))
    roadmaps_by_workspace: dict[uuid.UUID, list[dict[str, Any]]] = {
        workspace_id: [] for workspace_id in workspace_ids
    }
    for roadmap in roadmaps:
        roadmaps_by_workspace[roadmap.workspace_id].append(
            {
                "id": roadmap.id,
                "roadmap_type": roadmap.roadmap_type,
                "title": roadmap.title,
                "status": roadmap.status,
                "proposer": None
                if roadmap.proposer_user_id is None
                else ("self" if roadmap.proposer_user_id == user_id else "counterpart"),
                "created_at": roadmap.created_at,
                "updated_at": roadmap.updated_at,
                "milestones": milestones[roadmap.id],
            }
        )

    checkins = (
        (
            await db.execute(
                select(RelationshipCheckin)
                .where(RelationshipCheckin.workspace_id.in_(workspace_ids))
                .order_by(RelationshipCheckin.cycle_started_at)
            )
        )
        .scalars()
        .all()
    )
    checkin_ids = [checkin.id for checkin in checkins]
    own_responses: dict[uuid.UUID, list[dict[str, Any]]] = {
        checkin_id: [] for checkin_id in checkin_ids
    }
    analyses: dict[uuid.UUID, dict[str, Any]] = {}
    if checkin_ids:
        for row in (
            await db.execute(
                select(
                    CheckinResponse.checkin_id,
                    CheckinResponse.semantic_key,
                    CheckinResponse.value,
                    CheckinResponse.submitted_at,
                )
                .where(
                    CheckinResponse.checkin_id.in_(checkin_ids),
                    CheckinResponse.user_id == user_id,
                )
                .order_by(CheckinResponse.semantic_key)
            )
        ).mappings():
            own_responses[row["checkin_id"]].append(dict(row))
        for row in (
            await db.execute(
                select(
                    CheckinAnalysis.checkin_id,
                    CheckinAnalysis.checkin_template_version,
                    CheckinAnalysis.result_json,
                    CheckinAnalysis.computed_at,
                ).where(CheckinAnalysis.checkin_id.in_(checkin_ids))
            )
        ).mappings():
            analyses[row["checkin_id"]] = dict(row)

    shared_reflections = [
        dict(row)
        for row in (
            await db.execute(
                select(
                    SharedReflection.id,
                    SharedReflection.workspace_id,
                    SharedReflection.author_user_id,
                    SharedReflection.entry_date,
                    SharedReflection.content,
                    SharedReflection.shared_at,
                    SharedReflection.created_at,
                    SharedReflection.updated_at,
                )
                .where(SharedReflection.workspace_id.in_(workspace_ids))
                .order_by(SharedReflection.shared_at)
            )
        ).mappings()
    ]

    jobs = [
        dict(row)
        for row in (
            await db.execute(
                select(
                    AnalysisJob.id,
                    AnalysisJob.workspace_id,
                    AnalysisJob.analysis_type,
                    AnalysisJob.status,
                    AnalysisJob.progress,
                    AnalysisJob.attempt_count,
                    AnalysisJob.error_code,
                    AnalysisJob.requested_by_user_id,
                    AnalysisJob.created_at,
                )
                .where(AnalysisJob.workspace_id.in_(workspace_ids))
                .order_by(AnalysisJob.created_at)
            )
        ).mappings()
    ]

    relationship_analyses = [
        dict(row)
        for row in (
            await db.execute(
                select(
                    RelationshipAnalysis.workspace_id,
                    RelationshipAnalysis.job_id,
                    RelationshipAnalysis.relationship_type,
                    RelationshipAnalysis.status,
                    RelationshipAnalysis.calculation_version,
                    RelationshipAnalysis.knowledge_version,
                    RelationshipAnalysis.prompt_version,
                    RelationshipAnalysis.result_json,
                    RelationshipAnalysis.generated_at,
                    RelationshipAnalysis.created_at,
                )
                .where(RelationshipAnalysis.workspace_id.in_(workspace_ids))
                .order_by(RelationshipAnalysis.created_at)
            )
        ).mappings()
    ]
    shadow_analyses = [
        dict(row)
        for row in (
            await db.execute(
                select(
                    ShadowDynamicsAnalysis.workspace_id,
                    ShadowDynamicsAnalysis.job_id,
                    ShadowDynamicsAnalysis.relationship_type,
                    ShadowDynamicsAnalysis.status,
                    ShadowDynamicsAnalysis.calculation_version,
                    ShadowDynamicsAnalysis.knowledge_version,
                    ShadowDynamicsAnalysis.prompt_version,
                    ShadowDynamicsAnalysis.result_json,
                    ShadowDynamicsAnalysis.generated_at,
                    ShadowDynamicsAnalysis.created_at,
                )
                .where(ShadowDynamicsAnalysis.workspace_id.in_(workspace_ids))
                .order_by(ShadowDynamicsAnalysis.created_at)
            )
        ).mappings()
    ]

    threads = (
        (
            await db.execute(
                select(ChatThread)
                .where(
                    ChatThread.workspace_id.in_(workspace_ids),
                    (ChatThread.scope == ThreadScope.RELATIONSHIP_SHARED)
                    | (ChatThread.owner_user_id == user_id),
                )
                .order_by(ChatThread.created_at)
            )
        )
        .scalars()
        .all()
    )
    thread_messages = await _messages_for_threads(
        db, thread_ids=[thread.id for thread in threads], user_id=user_id
    )
    threads_by_workspace: dict[uuid.UUID, list[dict[str, Any]]] = {
        workspace_id: [] for workspace_id in workspace_ids
    }
    for thread in threads:
        if thread.workspace_id is None:
            # Kann durch den WHERE-Filter oben nicht passieren (nur Threads mit
            # workspace_id IN ... werden gelesen) -- die Pruefung existiert, damit der
            # Typchecker den Nullable-Fall nicht auf einen stillen None-Key abbildet.
            continue
        threads_by_workspace[thread.workspace_id].append(
            {
                "id": thread.id,
                "scope": thread.scope,
                "context_version": thread.context_version,
                "created_at": thread.created_at,
                "archived_at": thread.archived_at,
                "messages": thread_messages[thread.id],
            }
        )

    def _group(
        rows: list[dict[str, Any]], key: str, workspace_id: uuid.UUID
    ) -> list[dict[str, Any]]:
        return [row for row in rows if row[key] == workspace_id]

    result: list[dict[str, Any]] = []
    for workspace in workspaces:
        workspace_id = workspace.id
        result.append(
            {
                "id": workspace.id,
                "status": workspace.status,
                "relationship_type": workspace.relationship_type,
                "created_at": workspace.created_at,
                "dissolved_at": workspace.dissolved_at,
                "members": members_by_workspace[workspace_id],
                "consent": {
                    "grants": grants_by_workspace[workspace_id],
                    "events": events_by_workspace[workspace_id],
                },
                "tasks": tasks_by_workspace[workspace_id],
                "roadmaps": roadmaps_by_workspace[workspace_id],
                "checkins": [
                    {
                        "id": checkin.id,
                        "snapshot_origin": checkin.snapshot_origin,
                        "checkin_template_version": checkin.checkin_template_version,
                        "status": checkin.status,
                        "cycle_started_at": checkin.cycle_started_at,
                        "created_at": checkin.created_at,
                        "own_responses": own_responses[checkin.id],
                        "shared_analysis": analyses.get(checkin.id),
                    }
                    for checkin in checkins
                    if checkin.workspace_id == workspace_id
                ],
                "shared_reflections": [
                    {
                        **{key: value for key, value in row.items() if key != "author_user_id"},
                        "author": "self" if row["author_user_id"] == user_id else "counterpart",
                    }
                    for row in _group(shared_reflections, "workspace_id", workspace_id)
                ],
                "analysis_jobs": [
                    {
                        **{
                            key: value
                            for key, value in row.items()
                            if key != "requested_by_user_id"
                        },
                        "requested_by": "self"
                        if row["requested_by_user_id"] == user_id
                        else "counterpart",
                    }
                    for row in _group(jobs, "workspace_id", workspace_id)
                ],
                "analyses": {
                    "relationship": _group(relationship_analyses, "workspace_id", workspace_id),
                    "shadow_dynamics": _group(shadow_analyses, "workspace_id", workspace_id),
                },
                "copilot_threads": threads_by_workspace[workspace_id],
            }
        )
    return result
