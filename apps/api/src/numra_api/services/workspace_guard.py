"""PR-V2-10 -- der eine zentrale Guard, der eine content-erzeugende Workspace-
Mutation ablehnt, sobald der Workspace `DISSOLVED` ist. `WorkspaceDissolved` wird
IMMER erst NACH dem bestehenden `get_workspace_member`-IDOR-Gate ausgelöst (nie
davor) -- ein Nicht-Mitglied muss weiterhin einen 404 (`NotFoundError`) sehen, nie
einen 409, der die Existenz des Workspace verraten würde. GET/List-Funktionen rufen
diesen Guard nie auf -- ein `DISSOLVED`-Workspace bleibt für beide Mitglieder
lesbar (specs/v2/dissolution-policy.md: "future data access ends immediately",
history bleibt einsehbar).
"""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from numra_api.models import RelationshipWorkspace
from numra_api.models.enums import WorkspaceStatus
from numra_api.repositories.workspaces import get_workspace_by_id
from numra_api.services.errors import NotFoundError, WorkspaceDissolved

__all__ = ["assert_workspace_active", "assert_workspace_active_by_id"]


async def assert_workspace_active(db: AsyncSession, *, workspace: RelationshipWorkspace) -> None:
    if workspace.status == WorkspaceStatus.DISSOLVED:
        raise WorkspaceDissolved(f"workspace {workspace.id} is dissolved")


async def assert_workspace_active_by_id(
    db: AsyncSession, *, workspace_id: uuid.UUID
) -> RelationshipWorkspace:
    """Lade-und-prüfe-Variante für die Aufrufer, die den Workspace nicht ohnehin schon
    geladen haben. Ersetzt an jeder Mutations-Stelle die vierzeilige Load-plus-`assert
    is not None`-Wiederholung; das `NotFoundError` hier ist reine Absicherung -- der
    Aufrufer hat sein Membership-Gate bereits passiert, also existiert der Workspace."""
    workspace = await get_workspace_by_id(db, workspace_id=workspace_id)
    if workspace is None:
        raise NotFoundError(f"workspace {workspace_id} not found")
    await assert_workspace_active(db, workspace=workspace)
    return workspace
