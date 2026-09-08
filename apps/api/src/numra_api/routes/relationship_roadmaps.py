"""specs/v2/roadmap-spec.md -- Roadmaps (PR-V2-08). Every route gates on
`get_workspace_member` first (inside the service layer), returning 404 (never
403) for a non-member -- same IDOR pattern as routes/workspace_tasks.py. No
route exposes `create_avenyth_suggested_roadmap` (see
services/relationship_roadmap_service.py docstring)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from numra_api.deps import get_current_user, get_db, require_csrf
from numra_api.models import RelationshipRoadmap, RoadmapMilestone, User
from numra_api.models.enums import MilestoneType
from numra_api.schemas.roadmap import (
    RelationshipRoadmapCreateRequest,
    RelationshipRoadmapOut,
    RelationshipRoadmapPatchRequest,
    RoadmapMilestoneCreateRequest,
    RoadmapMilestoneOut,
    RoadmapMilestonePatchRequest,
)
from numra_api.services.relationship_roadmap_service import (
    create_milestone,
    create_roadmap,
    delete_milestone,
    delete_roadmap,
    get_milestone,
    get_roadmap,
    list_milestones,
    list_roadmaps,
    patch_milestone,
    patch_roadmap,
)

router = APIRouter(prefix="/v1/workspaces/{workspace_id}", tags=["relationship-roadmaps"])


def _roadmap_out(roadmap: RelationshipRoadmap) -> RelationshipRoadmapOut:
    return RelationshipRoadmapOut.model_validate(roadmap, from_attributes=True)


def _milestone_out(milestone: RoadmapMilestone) -> RoadmapMilestoneOut:
    return RoadmapMilestoneOut.model_validate(milestone, from_attributes=True)


@router.post(
    "/roadmaps",
    response_model=RelationshipRoadmapOut,
    status_code=201,
    dependencies=[Depends(require_csrf)],
)
async def create_roadmap_route(
    workspace_id: uuid.UUID,
    body: RelationshipRoadmapCreateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RelationshipRoadmapOut:
    roadmap = await create_roadmap(
        db,
        workspace_id=workspace_id,
        user_id=user.id,
        roadmap_type=body.roadmap_type,
        title=body.title,
    )
    return _roadmap_out(roadmap)


@router.get("/roadmaps", response_model=list[RelationshipRoadmapOut])
async def list_roadmaps_route(
    workspace_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[RelationshipRoadmapOut]:
    roadmaps = await list_roadmaps(
        db, workspace_id=workspace_id, user_id=user.id, limit=limit, offset=offset
    )
    return [_roadmap_out(r) for r in roadmaps]


@router.get("/roadmaps/{roadmap_id}", response_model=RelationshipRoadmapOut)
async def get_roadmap_route(
    workspace_id: uuid.UUID,
    roadmap_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RelationshipRoadmapOut:
    roadmap = await get_roadmap(
        db, workspace_id=workspace_id, user_id=user.id, roadmap_id=roadmap_id
    )
    return _roadmap_out(roadmap)


@router.patch(
    "/roadmaps/{roadmap_id}",
    response_model=RelationshipRoadmapOut,
    dependencies=[Depends(require_csrf)],
)
async def patch_roadmap_route(
    workspace_id: uuid.UUID,
    roadmap_id: uuid.UUID,
    body: RelationshipRoadmapPatchRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RelationshipRoadmapOut:
    roadmap = await patch_roadmap(
        db,
        workspace_id=workspace_id,
        user_id=user.id,
        roadmap_id=roadmap_id,
        title=body.title,
        roadmap_type=body.roadmap_type,
        status=body.status,
    )
    return _roadmap_out(roadmap)


@router.delete("/roadmaps/{roadmap_id}", status_code=204, dependencies=[Depends(require_csrf)])
async def delete_roadmap_route(
    workspace_id: uuid.UUID,
    roadmap_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    await delete_roadmap(db, workspace_id=workspace_id, user_id=user.id, roadmap_id=roadmap_id)


@router.post(
    "/roadmaps/{roadmap_id}/milestones",
    response_model=RoadmapMilestoneOut,
    status_code=201,
    dependencies=[Depends(require_csrf)],
)
async def create_milestone_route(
    workspace_id: uuid.UUID,
    roadmap_id: uuid.UUID,
    body: RoadmapMilestoneCreateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RoadmapMilestoneOut:
    milestone = await create_milestone(
        db,
        workspace_id=workspace_id,
        user_id=user.id,
        roadmap_id=roadmap_id,
        milestone_type=body.milestone_type,
        title=body.title,
        description=body.description,
        target_date=body.target_date,
        sequence=body.sequence,
    )
    return _milestone_out(milestone)


@router.get("/roadmaps/{roadmap_id}/milestones", response_model=list[RoadmapMilestoneOut])
async def list_milestones_route(
    workspace_id: uuid.UUID,
    roadmap_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    milestone_type: MilestoneType | None = Query(default=None),
) -> list[RoadmapMilestoneOut]:
    milestones = await list_milestones(
        db,
        workspace_id=workspace_id,
        user_id=user.id,
        roadmap_id=roadmap_id,
        milestone_type=milestone_type,
    )
    return [_milestone_out(m) for m in milestones]


@router.get("/roadmaps/{roadmap_id}/milestones/{milestone_id}", response_model=RoadmapMilestoneOut)
async def get_milestone_route(
    workspace_id: uuid.UUID,
    roadmap_id: uuid.UUID,
    milestone_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RoadmapMilestoneOut:
    milestone = await get_milestone(
        db,
        workspace_id=workspace_id,
        user_id=user.id,
        roadmap_id=roadmap_id,
        milestone_id=milestone_id,
    )
    return _milestone_out(milestone)


@router.patch(
    "/roadmaps/{roadmap_id}/milestones/{milestone_id}",
    response_model=RoadmapMilestoneOut,
    dependencies=[Depends(require_csrf)],
)
async def patch_milestone_route(
    workspace_id: uuid.UUID,
    roadmap_id: uuid.UUID,
    milestone_id: uuid.UUID,
    body: RoadmapMilestonePatchRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RoadmapMilestoneOut:
    set_fields = body.model_fields_set
    milestone = await patch_milestone(
        db,
        workspace_id=workspace_id,
        user_id=user.id,
        roadmap_id=roadmap_id,
        milestone_id=milestone_id,
        title=body.title if "title" in set_fields else None,
        description=body.description,
        description_set="description" in set_fields,
        target_date=body.target_date,
        target_date_set="target_date" in set_fields,
        sequence=body.sequence,
        status=body.status,
    )
    return _milestone_out(milestone)


@router.delete(
    "/roadmaps/{roadmap_id}/milestones/{milestone_id}",
    status_code=204,
    dependencies=[Depends(require_csrf)],
)
async def delete_milestone_route(
    workspace_id: uuid.UUID,
    roadmap_id: uuid.UUID,
    milestone_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    await delete_milestone(
        db,
        workspace_id=workspace_id,
        user_id=user.id,
        roadmap_id=roadmap_id,
        milestone_id=milestone_id,
    )
