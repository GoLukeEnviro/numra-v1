"""PR-V2-10 -- Account-Löschung als Soft-Delete mit PII-Scrub.

Der frühere Weg (`DELETE FROM users`, Rest per FK-Kaskade) ist mit geteilten
Relationship-Daten unvereinbar: er hätte dem verbliebenen Partner Tasks, Roadmaps,
geteilte Reflexionen und den gemeinsamen Copilot-Thread mit weggerissen. Stattdessen
wird jede rein private Kindtabelle explizit gelöscht, die User-Row überlebt als
getilgter Tombstone, und der Partner sieht ab jetzt nur noch das Pseudonym
`repositories/account.py::DELETED_DISPLAY_NAME`.

Alles läuft in der einen request-scoped Session, die `deps.get_db` am Ende committet --
kein manuelles `db.begin()`, keine Teil-Löschung, die überleben könnte.
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy.ext.asyncio import AsyncSession

from numra_api.models import User
from numra_api.repositories.account import (
    delete_private_chat_threads,
    delete_private_content,
    delete_private_reports_and_exports,
    delete_profiles_and_credentials,
    mark_memberships_removed,
    scrub_user_pii,
)
from numra_api.repositories.connections import conditionally_dissolve_connection
from numra_api.repositories.exports import list_file_refs_for_user
from numra_api.repositories.workspaces import (
    conditionally_dissolve_workspace,
    list_workspaces_for_user,
)
from numra_api.services.consent_service import revoke_all_workspace_consent
from numra_api.storage.exports import ExportStorage

__all__ = ["delete_own_account"]


async def delete_own_account(db: AsyncSession, *, user: User, storage: ExportStorage) -> None:
    """Die Reauth (Passwort-Bestätigung) ist bereits in routes/account.py passiert.

    Physische Export-Dateien zuerst: schlägt eine Löschung fehl, bricht der Request ab,
    bevor irgendeine DB-Row angefasst wurde -- statt dass die DB "alles gelöscht" meldet,
    während eine Datei auf der Platte liegen bleibt (`ExportStorage.delete` ist
    idempotent, die Schleife ist also wiederholbar).
    """
    for file_ref in await list_file_refs_for_user(db, user_id=user.id):
        await storage.delete(file_ref)

    now = dt.datetime.now(dt.UTC)
    await _dissolve_workspaces_and_revoke_consent(db, user=user, now=now)

    await delete_private_reports_and_exports(db, user_id=user.id)
    await delete_private_content(db, user_id=user.id)
    await delete_private_chat_threads(db, user_id=user.id)
    await delete_profiles_and_credentials(db, user_id=user.id)

    await mark_memberships_removed(db, user_id=user.id)
    await scrub_user_pii(db, user=user, now=now)


async def _dissolve_workspaces_and_revoke_consent(
    db: AsyncSession, *, user: User, now: dt.datetime
) -> None:
    """Jeder Workspace, in dem der Löschende (noch) Mitglied ist, wird genauso
    aufgelöst wie bei einem expliziten Dissolve (`connection_service.py::
    dissolve_own_connection`) -- sonst bliebe `RelationshipWorkspace.status` ACTIVE
    und `workspace_guard.py::assert_workspace_active_by_id` ließe den verbliebenen
    Partner weiterhin neue geteilte Tasks/Roadmaps/Check-in-Runden gegen einen
    Ghost-User anlegen (specs/v2/dissolution-policy.md: "Future shared operations:
    DISABLED"). Dieselbe Konsistenz wie beim regulären Dissolve: erst die
    `UserConnection`, dann der `RelationshipWorkspace`, dann der kaskadierende
    Consent-Revoke -- alle drei über die bereits atomaren/TOCTOU-sicheren
    Primitiven. Muss VOR `mark_memberships_removed` laufen: `list_workspaces_for_user`
    findet die Workspaces über die noch-ACTIVE Membership.
    """
    for workspace in await list_workspaces_for_user(db, user_id=user.id):
        await conditionally_dissolve_connection(db, connection_id=workspace.connection_id, now=now)
        await conditionally_dissolve_workspace(db, workspace_id=workspace.id, now=now)
        await revoke_all_workspace_consent(
            db, workspace_id=workspace.id, actor_user_id=user.id, now=now
        )
