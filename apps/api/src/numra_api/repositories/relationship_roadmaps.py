"""PR-V2-08 -- specs/v2/roadmap-spec.md. Both `RelationshipRoadmap` and
`RoadmapMilestone` are workspace-wide visible (no proposer/recipient split, see
services/relationship_roadmap_service.py) -- callers still gate on
`get_workspace_member` first (IDOR anti-enumeration), same discipline as
repositories/workspace_tasks.py.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from numra_api.models import RelationshipRoadmap, RoadmapMilestone
from numra_api.models.enums import RoadmapStatus


async def create_roadmap(db: AsyncSession, **fields: Any) -> RelationshipRoadmap:
    roadmap = RelationshipRoadmap(**fields)
    db.add(roadmap)
    await db.flush()
    return roadmap


async def get_roadmap_for_workspace(
    db: AsyncSession, *, roadmap_id: uuid.UUID, workspace_id: uuid.UUID
) -> RelationshipRoadmap | None:
    stmt = select(RelationshipRoadmap).where(
        RelationshipRoadmap.id == roadmap_id, RelationshipRoadmap.workspace_id == workspace_id
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def list_roadmaps_for_workspace(
    db: AsyncSession, *, workspace_id: uuid.UUID, limit: int, offset: int
) -> list[RelationshipRoadmap]:
    stmt = (
        select(RelationshipRoadmap)
        .where(RelationshipRoadmap.workspace_id == workspace_id)
        .order_by(RelationshipRoadmap.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def update_roadmap(
    db: AsyncSession, *, roadmap: RelationshipRoadmap, **fields: Any
) -> RelationshipRoadmap:
    for key, value in fields.items():
        setattr(roadmap, key, value)
    await db.flush()
    await db.refresh(roadmap)
    return roadmap


async def conditionally_transition_roadmap_status(
    db: AsyncSession,
    *,
    roadmap_id: uuid.UUID,
    expected_status: RoadmapStatus,
    new_status: RoadmapStatus,
) -> bool:
    """Atomic `UPDATE ... WHERE id=? AND status=?` -- same TOCTOU-safety rationale
    as repositories/workspace_tasks.py::conditionally_transition_status. `False`
    means someone else already moved the roadmap out of `expected_status`."""
    stmt = (
        update(RelationshipRoadmap)
        .where(RelationshipRoadmap.id == roadmap_id, RelationshipRoadmap.status == expected_status)
        .values(status=new_status)
        .returning(RelationshipRoadmap.id)
    )
    result = await db.execute(stmt)
    await db.flush()
    return result.scalar_one_or_none() is not None


async def conditionally_archive_roadmap(db: AsyncSession, *, roadmap_id: uuid.UUID) -> bool:
    """Atomic `UPDATE ... WHERE id=? AND status <> ARCHIVED` -- ARCHIVED is
    reachable from any non-terminal status (PROPOSED or ACCEPTED,
    specs/v2/roadmap-spec.md Acceptance checks), so this is a `<>` guard rather
    than a single `expected_status` like
    `conditionally_transition_roadmap_status`. `False` means the roadmap was
    already ARCHIVED."""
    stmt = (
        update(RelationshipRoadmap)
        .where(
            RelationshipRoadmap.id == roadmap_id,
            RelationshipRoadmap.status != RoadmapStatus.ARCHIVED,
        )
        .values(status=RoadmapStatus.ARCHIVED)
        .returning(RelationshipRoadmap.id)
    )
    result = await db.execute(stmt)
    await db.flush()
    return result.scalar_one_or_none() is not None


async def delete_roadmap(db: AsyncSession, *, roadmap: RelationshipRoadmap) -> None:
    await db.delete(roadmap)


async def create_milestone(db: AsyncSession, **fields: Any) -> RoadmapMilestone:
    milestone = RoadmapMilestone(**fields)
    db.add(milestone)
    await db.flush()
    return milestone


async def get_milestone_for_roadmap(
    db: AsyncSession, *, milestone_id: uuid.UUID, roadmap_id: uuid.UUID
) -> RoadmapMilestone | None:
    stmt = select(RoadmapMilestone).where(
        RoadmapMilestone.id == milestone_id, RoadmapMilestone.roadmap_id == roadmap_id
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def get_milestone_in_workspace(
    db: AsyncSession, *, milestone_id: uuid.UUID, workspace_id: uuid.UUID
) -> RoadmapMilestone | None:
    """Used by repositories/workspace_tasks.py to validate a
    `roadmap_milestone_id` link belongs to the same workspace as the task
    (specs/v2 build order: Task<->Milestone link, Cross-Workspace -> 422/404)."""
    stmt = (
        select(RoadmapMilestone)
        .join(RelationshipRoadmap, RelationshipRoadmap.id == RoadmapMilestone.roadmap_id)
        .where(
            RoadmapMilestone.id == milestone_id,
            RelationshipRoadmap.workspace_id == workspace_id,
        )
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def list_milestones_for_roadmap(
    db: AsyncSession, *, roadmap_id: uuid.UUID, milestone_type: str | None
) -> list[RoadmapMilestone]:
    stmt = select(RoadmapMilestone).where(RoadmapMilestone.roadmap_id == roadmap_id)
    if milestone_type is not None:
        stmt = stmt.where(RoadmapMilestone.milestone_type == milestone_type)
    stmt = stmt.order_by(RoadmapMilestone.sequence.asc())
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def update_milestone(
    db: AsyncSession, *, milestone: RoadmapMilestone, **fields: Any
) -> RoadmapMilestone:
    for key, value in fields.items():
        setattr(milestone, key, value)
    await db.flush()
    await db.refresh(milestone)
    return milestone


async def delete_milestone(db: AsyncSession, *, milestone: RoadmapMilestone) -> None:
    await db.delete(milestone)
