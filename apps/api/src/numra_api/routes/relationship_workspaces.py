"""GET/PATCH /v1/workspaces/{workspace_id} + GET /v1/workspaces -- Relationship
Workspace OVERVIEW + DUAL PROFILE + relationship_type. Deliberately separate from
routes/workspace.py (that is the Personal Workspace at /v1/me/workspace, a different
concept -- see that module's own docstring)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from numra_api.deps import get_current_user, get_db, require_csrf
from numra_api.models import RelationshipWorkspace, User
from numra_api.schemas.relationship_workspace import (
    WorkspaceOut,
    WorkspaceOverviewOut,
    WorkspaceSummaryOut,
    WorkspaceUpdateRequest,
)
from numra_api.services.feature_flags import require_v2_phase
from numra_api.services.relationship_workspace_service import (
    get_workspace_overview,
    list_workspaces_for_viewer,
    patch_relationship_type,
)

router = APIRouter(
    prefix="/v1/workspaces",
    tags=["relationship-workspaces"],
    dependencies=[Depends(require_v2_phase("relationship_workspaces"))],
)


def _workspace_to_out(workspace: RelationshipWorkspace) -> WorkspaceOut:
    return WorkspaceOut.model_validate(workspace, from_attributes=True)


def _workspace_to_summary(workspace: RelationshipWorkspace) -> WorkspaceSummaryOut:
    return WorkspaceSummaryOut.model_validate(workspace, from_attributes=True)


@router.get("", response_model=list[WorkspaceSummaryOut])
async def list_workspaces_route(
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> list[WorkspaceSummaryOut]:
    workspaces = await list_workspaces_for_viewer(db, user_id=user.id)
    return [_workspace_to_summary(w) for w in workspaces]


@router.get("/{workspace_id}", response_model=WorkspaceOverviewOut)
async def get_workspace_overview_route(
    workspace_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WorkspaceOverviewOut:
    workspace, dual_profile = await get_workspace_overview(
        db, workspace_id=workspace_id, viewer_user_id=user.id
    )
    return WorkspaceOverviewOut(workspace=_workspace_to_out(workspace), dual_profile=dual_profile)


@router.patch("/{workspace_id}", response_model=WorkspaceOut, dependencies=[Depends(require_csrf)])
async def patch_workspace_route(
    workspace_id: uuid.UUID,
    body: WorkspaceUpdateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WorkspaceOut:
    workspace = await patch_relationship_type(
        db,
        workspace_id=workspace_id,
        user_id=user.id,
        relationship_type=body.relationship_type,
    )
    return _workspace_to_out(workspace)
