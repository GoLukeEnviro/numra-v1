"""specs/v2/personal-workspace-spec.md SHARE flow (PR-V2-08). Every route gates
on `get_workspace_member` first (inside the service layer), returning 404
(never 403) for a non-member -- same IDOR pattern as
routes/relationship_roadmaps.py. The actual creation endpoint
(POST /v1/private-reflections/{reflection_id}/share) lives on
routes/private_reflections.py -- there is no direct-compose create route here."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from numra_api.deps import get_current_user, get_db, require_csrf
from numra_api.models import SharedReflection, User
from numra_api.schemas.shared_reflection import SharedReflectionOut
from numra_api.services.shared_reflection_service import (
    delete_shared_reflection,
    get_shared_reflection,
    list_shared_reflections,
)

router = APIRouter(prefix="/v1/workspaces/{workspace_id}", tags=["shared-reflections"])


def _to_out(reflection: SharedReflection) -> SharedReflectionOut:
    return SharedReflectionOut.model_validate(reflection, from_attributes=True)


@router.get("/shared-reflections", response_model=list[SharedReflectionOut])
async def list_shared_reflections_route(
    workspace_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[SharedReflectionOut]:
    reflections = await list_shared_reflections(
        db, workspace_id=workspace_id, user_id=user.id, limit=limit, offset=offset
    )
    return [_to_out(r) for r in reflections]


@router.get("/shared-reflections/{reflection_id}", response_model=SharedReflectionOut)
async def get_shared_reflection_route(
    workspace_id: uuid.UUID,
    reflection_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SharedReflectionOut:
    reflection = await get_shared_reflection(
        db, workspace_id=workspace_id, user_id=user.id, reflection_id=reflection_id
    )
    return _to_out(reflection)


@router.delete(
    "/shared-reflections/{reflection_id}", status_code=204, dependencies=[Depends(require_csrf)]
)
async def delete_shared_reflection_route(
    workspace_id: uuid.UUID,
    reflection_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    await delete_shared_reflection(
        db, workspace_id=workspace_id, user_id=user.id, reflection_id=reflection_id
    )
