"""PR-V2-10 -- die Schreib-Primitiven der Account-Löschung (Soft-Delete + PII-Scrub).

Ersetzt den früheren `delete_all_user_data`-Bare-Cascade (`DELETE FROM users` und die
DB räumt alles ab). Der User-Row überlebt jetzt bewusst als getilgter Tombstone, damit
die FKs geteilter Relationship-Artefakte (`WorkspaceMember`, `ConsentGrant`,
`WorkspaceTask`, `RelationshipRoadmap`, `SharedReflection`, `AnalysisJob`) gültig
bleiben und der Partner seine gemeinsame Historie behält -- also muss jede rein private
Kindtabelle explizit gelöscht werden, statt sich auf `ondelete=CASCADE` zu verlassen.

Reihenfolge: Kinder vor Eltern. Wo eine FK-Kaskade den Rest zuverlässig mitnimmt
(`report_sections`/`llm_generations` unter `reports`/`report_jobs`, `name_identities`/
`calculations` unter `people`), ist das am jeweiligen Aufruf vermerkt.
"""

from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import delete, update
from sqlalchemy.ext.asyncio import AsyncSession

from numra_api.auth.passwords import hash_password
from numra_api.auth.tokens import generate_token
from numra_api.models import (
    ChatThread,
    CheckinResponse,
    EmailVerificationToken,
    Export,
    PasswordResetToken,
    Person,
    PersonalTask,
    PrivateNote,
    PrivateReflection,
    RelationshipComparison,
    Report,
    ReportJob,
    Session,
    User,
    WorkspaceMember,
)
from numra_api.models.enums import ThreadScope, WorkspaceMemberStatus

#: specs/v2/privacy-spec.md -- der Anzeigename, den der verbliebene Partner ab jetzt
#: überall statt der Original-E-Mail sieht (siehe
#: services/relationship_workspace_service.py::_fallback_display_name).
DELETED_DISPLAY_NAME = "Ehemaliges Mitglied"

#: Nie ein echter Mailbox-Namespace: `.invalid` ist per RFC 2606 reserviert, ein Versand
#: dorthin kann also nie versehentlich zugestellt werden.
_DELETED_EMAIL_DOMAIN = "deleted.avenyth.invalid"


async def delete_private_reports_and_exports(db: AsyncSession, *, user_id: uuid.UUID) -> None:
    """`report_sections` und `llm_generations` hängen per `ondelete=CASCADE` an
    `reports` bzw. `report_jobs` und gehen mit."""
    await db.execute(delete(ReportJob).where(ReportJob.user_id == user_id))
    await db.execute(delete(Report).where(Report.user_id == user_id))
    await db.execute(delete(Export).where(Export.user_id == user_id))


async def delete_private_content(db: AsyncSession, *, user_id: uuid.UUID) -> None:
    """Ausschließlich alleinbesessene Inhalte. `CheckinResponse` ist die eigene
    Einreichung des Users; `CheckinAnalysis` hat keine `user_id` und ist das geteilte,
    abgeleitete Ergebnis -- bleibt daher unangetastet."""
    await db.execute(
        delete(RelationshipComparison).where(RelationshipComparison.user_id == user_id)
    )
    await db.execute(delete(PersonalTask).where(PersonalTask.user_id == user_id))
    await db.execute(delete(PrivateNote).where(PrivateNote.user_id == user_id))
    await db.execute(delete(PrivateReflection).where(PrivateReflection.user_id == user_id))
    await db.execute(delete(CheckinResponse).where(CheckinResponse.user_id == user_id))


async def delete_private_chat_threads(db: AsyncSession, *, user_id: uuid.UUID) -> None:
    """Nur die beiden privaten Scopes, immer owner-gefiltert. `RELATIONSHIP_SHARED` hat
    per CHECK-Constraint gar keinen `owner_user_id` und wird hier nie getroffen -- der
    gemeinsame Thread gehört beiden und bleibt für den Partner lesbar.
    `ChatMessage`/`ThreadContextSnapshot`/`ThreadSummary` kaskadieren am `thread_id`."""
    await db.execute(
        delete(ChatThread).where(
            ChatThread.owner_user_id == user_id,
            ChatThread.scope.in_((ThreadScope.PERSONAL_PRIVATE, ThreadScope.RELATIONSHIP_PRIVATE)),
        )
    )


async def delete_profiles_and_credentials(db: AsyncSession, *, user_id: uuid.UUID) -> None:
    """`people` nimmt `name_identities` und `calculations` per FK-Kaskade mit -- das
    deckt zugleich die verwalteten Profile (MANAGED_MINOR/MANAGED_OTHER) ab, die
    ebenfalls alleinbesessen sind."""
    await db.execute(delete(Person).where(Person.user_id == user_id))
    await db.execute(delete(Session).where(Session.user_id == user_id))
    await db.execute(
        delete(EmailVerificationToken).where(EmailVerificationToken.user_id == user_id)
    )
    await db.execute(delete(PasswordResetToken).where(PasswordResetToken.user_id == user_id))


async def mark_memberships_removed(db: AsyncSession, *, user_id: uuid.UUID) -> None:
    """Die Membership-Row bleibt bestehen (der Partner behält den Kontext, wer im
    Workspace war), verliert aber ihren ACTIVE-Status -- damit fällt der User aus jedem
    `get_workspace_member`-Gate heraus, ohne dass irgendein Fremdschlüssel bricht."""
    await db.execute(
        update(WorkspaceMember)
        .where(
            WorkspaceMember.user_id == user_id,
            WorkspaceMember.status == WorkspaceMemberStatus.ACTIVE,
        )
        .values(status=WorkspaceMemberStatus.REMOVED)
    )


async def scrub_user_pii(db: AsyncSession, *, user: User, now: dt.datetime) -> None:
    """Der eigentliche Löschakt auf der überlebenden User-Row. Die E-Mail wird durch
    eine eindeutige Wegwerf-Adresse ersetzt -- das gibt die Original-Adresse für eine
    Neuregistrierung frei UND hält den Unique-Index auf `users.email` kollisionsfrei,
    falls derselbe Mensch später erneut löscht. Das Passwort-Hash wird auf ein
    zufälliges Geheimnis gesetzt (nicht geleert), damit kein Vergleichspfad je auf einen
    leeren/konstanten Wert trifft."""
    user.email = f"deleted+{uuid.uuid4()}@{_DELETED_EMAIL_DOMAIN}"
    user.password_hash = hash_password(generate_token())
    user.is_active = False
    user.deleted_at = now
    user.display_name_override = DELETED_DISPLAY_NAME
    await db.flush()
