"""PR-V2-08 -- specs/v2/roadmap-spec.md. Server-authoritative state machine for
`RelationshipRoadmap`/`RoadmapMilestone`. NO LLM import anywhere in this module --
an AVENYTH-proposed roadmap is only ever a data structure written by
`create_avenyth_suggested_roadmap` (an internal function, no route exposes it);
the caller that eventually wires an analysis pipeline to it is out of scope for
this PR. Both entities are workspace-wide visible to any ACTIVE member (no
proposer/recipient split, unlike `WorkspaceTask`) -- specs/v2/api-contract.md PR
structure."""

from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

import numra_api.repositories.relationship_roadmaps as roadmaps_repo
from numra_api.models import RelationshipRoadmap, RoadmapMilestone
from numra_api.models.enums import MilestoneStatus, RoadmapStatus, RoadmapType
from numra_api.repositories.workspaces import get_workspace_member
from numra_api.services.errors import (
    InvalidRoadmapStatusTransition,
    NotFoundError,
    RoadmapArchived,
    RoadmapNotDeletable,
    RoadmapTransitionConflict,
)
from numra_api.services.workspace_guard import assert_workspace_active_by_id

#: PATCH .../roadmaps/{roadmap_id} may only move status into one of these two
#: values -- see docstring on routes/relationship_roadmaps.py.
_PATCHABLE_ROADMAP_STATUSES = frozenset({RoadmapStatus.ACCEPTED, RoadmapStatus.ARCHIVED})

#: DELETE .../roadmaps/{roadmap_id} is only allowed while the roadmap never
#: became (or is no longer) accepted shared work.
_DELETABLE_ROADMAP_STATUSES = frozenset({RoadmapStatus.PROPOSED, RoadmapStatus.ARCHIVED})


def _require_member(member: object, *, workspace_id: uuid.UUID) -> None:
    if member is None:
        # IDOR-anti-enumeration -- never 403, see services/workspace_task_service.py.
        raise NotFoundError(f"workspace {workspace_id} not found")


def _require_roadmap(
    roadmap: RelationshipRoadmap | None, *, roadmap_id: uuid.UUID
) -> RelationshipRoadmap:
    if roadmap is None:
        raise NotFoundError(f"roadmap {roadmap_id} not found")
    return roadmap


def _require_milestone(
    milestone: RoadmapMilestone | None, *, milestone_id: uuid.UUID
) -> RoadmapMilestone:
    if milestone is None:
        raise NotFoundError(f"milestone {milestone_id} not found")
    return milestone


async def create_roadmap(
    db: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
    roadmap_type: RoadmapType,
    title: str,
) -> RelationshipRoadmap:
    member = await get_workspace_member(db, workspace_id=workspace_id, user_id=user_id)
    _require_member(member, workspace_id=workspace_id)

    await assert_workspace_active_by_id(db, workspace_id=workspace_id)

    return await roadmaps_repo.create_roadmap(
        db,
        workspace_id=workspace_id,
        roadmap_type=roadmap_type,
        title=title,
        status=RoadmapStatus.PROPOSED,
        proposer_user_id=user_id,
    )


async def create_avenyth_suggested_roadmap(
    db: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    roadmap_type: RoadmapType,
    title: str,
    source_analysis_id: uuid.UUID,
    prompt_version: str,
    knowledge_version: str,
) -> RelationshipRoadmap:
    """Internal-only creation path -- no route calls this. Never sets `status` to
    anything but PROPOSED; only an explicit user PATCH (accept/archive) can move
    it further (specs/v2/roadmap-spec.md: "never pre-marked complete")."""
    await assert_workspace_active_by_id(db, workspace_id=workspace_id)

    return await roadmaps_repo.create_roadmap(
        db,
        workspace_id=workspace_id,
        roadmap_type=roadmap_type,
        title=title,
        status=RoadmapStatus.PROPOSED,
        proposer_user_id=None,
        source_analysis_id=source_analysis_id,
        prompt_version=prompt_version,
        knowledge_version=knowledge_version,
    )


async def get_roadmap(
    db: AsyncSession, *, workspace_id: uuid.UUID, user_id: uuid.UUID, roadmap_id: uuid.UUID
) -> RelationshipRoadmap:
    member = await get_workspace_member(db, workspace_id=workspace_id, user_id=user_id)
    _require_member(member, workspace_id=workspace_id)

    roadmap = await roadmaps_repo.get_roadmap_for_workspace(
        db, roadmap_id=roadmap_id, workspace_id=workspace_id
    )
    return _require_roadmap(roadmap, roadmap_id=roadmap_id)


async def list_roadmaps(
    db: AsyncSession, *, workspace_id: uuid.UUID, user_id: uuid.UUID, limit: int, offset: int
) -> list[RelationshipRoadmap]:
    member = await get_workspace_member(db, workspace_id=workspace_id, user_id=user_id)
    _require_member(member, workspace_id=workspace_id)

    return await roadmaps_repo.list_roadmaps_for_workspace(
        db, workspace_id=workspace_id, limit=limit, offset=offset
    )


async def patch_roadmap(
    db: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
    roadmap_id: uuid.UUID,
    title: str | None,
    roadmap_type: RoadmapType | None,
    status: RoadmapStatus | None,
) -> RelationshipRoadmap:
    member = await get_workspace_member(db, workspace_id=workspace_id, user_id=user_id)
    _require_member(member, workspace_id=workspace_id)

    await assert_workspace_active_by_id(db, workspace_id=workspace_id)

    roadmap = await roadmaps_repo.get_roadmap_for_workspace(
        db, roadmap_id=roadmap_id, workspace_id=workspace_id
    )
    roadmap = _require_roadmap(roadmap, roadmap_id=roadmap_id)

    updates: dict[str, object] = {}
    if title is not None or roadmap_type is not None:
        if roadmap.status == RoadmapStatus.ARCHIVED:
            raise RoadmapArchived(f"roadmap {roadmap_id} is archived and read-only")
        if title is not None:
            updates["title"] = title
        if roadmap_type is not None:
            updates["roadmap_type"] = roadmap_type
    if updates:
        roadmap = await roadmaps_repo.update_roadmap(db, roadmap=roadmap, **updates)

    if status is not None:
        if status not in _PATCHABLE_ROADMAP_STATUSES:
            raise InvalidRoadmapStatusTransition(
                f"status {status} cannot be set directly via PATCH"
            )
        if status == RoadmapStatus.ACCEPTED:
            won = await roadmaps_repo.conditionally_transition_roadmap_status(
                db,
                roadmap_id=roadmap.id,
                expected_status=RoadmapStatus.PROPOSED,
                new_status=RoadmapStatus.ACCEPTED,
            )
        else:
            won = await roadmaps_repo.conditionally_archive_roadmap(db, roadmap_id=roadmap.id)
        if not won:
            raise RoadmapTransitionConflict(f"roadmap {roadmap_id} cannot transition to {status}")
        await db.refresh(roadmap)

    return roadmap


async def delete_roadmap(
    db: AsyncSession, *, workspace_id: uuid.UUID, user_id: uuid.UUID, roadmap_id: uuid.UUID
) -> None:
    member = await get_workspace_member(db, workspace_id=workspace_id, user_id=user_id)
    _require_member(member, workspace_id=workspace_id)

    roadmap = await roadmaps_repo.get_roadmap_for_workspace(
        db, roadmap_id=roadmap_id, workspace_id=workspace_id
    )
    roadmap = _require_roadmap(roadmap, roadmap_id=roadmap_id)

    if roadmap.status not in _DELETABLE_ROADMAP_STATUSES:
        raise RoadmapNotDeletable(
            f"roadmap {roadmap_id} in state {roadmap.status} cannot be deleted"
        )

    await roadmaps_repo.delete_roadmap(db, roadmap=roadmap)


async def _require_roadmap_for_workspace(
    db: AsyncSession, *, workspace_id: uuid.UUID, roadmap_id: uuid.UUID
) -> RelationshipRoadmap:
    roadmap = await roadmaps_repo.get_roadmap_for_workspace(
        db, roadmap_id=roadmap_id, workspace_id=workspace_id
    )
    return _require_roadmap(roadmap, roadmap_id=roadmap_id)


async def create_milestone(
    db: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
    roadmap_id: uuid.UUID,
    milestone_type: str,
    title: str,
    description: str | None,
    target_date: dt.date | None,
    sequence: int,
) -> RoadmapMilestone:
    member = await get_workspace_member(db, workspace_id=workspace_id, user_id=user_id)
    _require_member(member, workspace_id=workspace_id)

    await assert_workspace_active_by_id(db, workspace_id=workspace_id)

    await _require_roadmap_for_workspace(db, workspace_id=workspace_id, roadmap_id=roadmap_id)

    return await roadmaps_repo.create_milestone(
        db,
        roadmap_id=roadmap_id,
        milestone_type=milestone_type,
        title=title,
        description=description,
        target_date=target_date,
        sequence=sequence,
        status=MilestoneStatus.PENDING,
    )


async def get_milestone(
    db: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
    roadmap_id: uuid.UUID,
    milestone_id: uuid.UUID,
) -> RoadmapMilestone:
    member = await get_workspace_member(db, workspace_id=workspace_id, user_id=user_id)
    _require_member(member, workspace_id=workspace_id)
    await _require_roadmap_for_workspace(db, workspace_id=workspace_id, roadmap_id=roadmap_id)

    milestone = await roadmaps_repo.get_milestone_for_roadmap(
        db, milestone_id=milestone_id, roadmap_id=roadmap_id
    )
    return _require_milestone(milestone, milestone_id=milestone_id)


async def list_milestones(
    db: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
    roadmap_id: uuid.UUID,
    milestone_type: str | None,
) -> list[RoadmapMilestone]:
    member = await get_workspace_member(db, workspace_id=workspace_id, user_id=user_id)
    _require_member(member, workspace_id=workspace_id)
    await _require_roadmap_for_workspace(db, workspace_id=workspace_id, roadmap_id=roadmap_id)

    return await roadmaps_repo.list_milestones_for_roadmap(
        db, roadmap_id=roadmap_id, milestone_type=milestone_type
    )


async def patch_milestone(
    db: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
    roadmap_id: uuid.UUID,
    milestone_id: uuid.UUID,
    title: str | None,
    description: str | None,
    description_set: bool,
    target_date: dt.date | None,
    target_date_set: bool,
    sequence: int | None,
    status: MilestoneStatus | None,
) -> RoadmapMilestone:
    member = await get_workspace_member(db, workspace_id=workspace_id, user_id=user_id)
    _require_member(member, workspace_id=workspace_id)

    await assert_workspace_active_by_id(db, workspace_id=workspace_id)

    await _require_roadmap_for_workspace(db, workspace_id=workspace_id, roadmap_id=roadmap_id)

    milestone = await roadmaps_repo.get_milestone_for_roadmap(
        db, milestone_id=milestone_id, roadmap_id=roadmap_id
    )
    milestone = _require_milestone(milestone, milestone_id=milestone_id)

    updates: dict[str, object] = {}
    if title is not None:
        updates["title"] = title
    if description_set:
        updates["description"] = description
    if target_date_set:
        updates["target_date"] = target_date
    if sequence is not None:
        updates["sequence"] = sequence

    if status is not None:
        updates["status"] = status
        # completed_at is server-derived, never client-supplied -- only an
        # explicit user PATCH may set it (specs/v2/roadmap-spec.md: "never
        # marks a milestone ... as fulfilled" automatically/via LLM).
        if status == MilestoneStatus.COMPLETED:
            updates["completed_at"] = dt.datetime.now(dt.UTC)
        elif milestone.status == MilestoneStatus.COMPLETED:
            updates["completed_at"] = None

    if updates:
        milestone = await roadmaps_repo.update_milestone(db, milestone=milestone, **updates)
    return milestone


async def delete_milestone(
    db: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
    roadmap_id: uuid.UUID,
    milestone_id: uuid.UUID,
) -> None:
    member = await get_workspace_member(db, workspace_id=workspace_id, user_id=user_id)
    _require_member(member, workspace_id=workspace_id)
    await _require_roadmap_for_workspace(db, workspace_id=workspace_id, roadmap_id=roadmap_id)

    milestone = await roadmaps_repo.get_milestone_for_roadmap(
        db, milestone_id=milestone_id, roadmap_id=roadmap_id
    )
    milestone = _require_milestone(milestone, milestone_id=milestone_id)

    await roadmaps_repo.delete_milestone(db, milestone=milestone)


__all__ = [
    "create_avenyth_suggested_roadmap",
    "create_milestone",
    "create_roadmap",
    "delete_milestone",
    "delete_roadmap",
    "get_milestone",
    "get_roadmap",
    "list_milestones",
    "list_roadmaps",
    "patch_milestone",
    "patch_roadmap",
]
