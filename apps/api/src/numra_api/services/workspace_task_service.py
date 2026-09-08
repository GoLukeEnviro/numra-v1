"""PR-V2-07 -- specs/v2/task-system-spec.md. Server-authoritative state machine
for `WorkspaceTask`. NO LLM import anywhere in this module -- `AVENYTH_SUGGESTED`
is only ever a data structure written by `create_avenyth_suggestion` (an
internal function, no route exposes it); the caller that eventually wires an
analysis pipeline to it is out of scope for this PR.
"""

from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

import numra_api.repositories.relationship_roadmaps as roadmaps_repo
import numra_api.repositories.workspace_tasks as tasks_repo
from numra_api.models import WorkspaceTask
from numra_api.models.enums import TaskAcceptanceEventType, TaskType, WorkspaceTaskStatus
from numra_api.repositories.workspaces import get_workspace_member, list_workspace_members
from numra_api.services.errors import (
    AvenythSuggestedNotUserCreatable,
    InvalidRecipient,
    MilestoneNotInWorkspace,
    NotFoundError,
    TaskNotDeletable,
    TaskTransitionConflict,
)

#: PATCH .../tasks/{task_id} may only move status into one of these two terminal-
#: ish states -- PROPOSED/ACCEPTED/ACTIVE transitions are exclusively driven by
#: accept/decline, never by a free-form PATCH.
_PATCHABLE_STATUSES = frozenset({WorkspaceTaskStatus.COMPLETED, WorkspaceTaskStatus.ARCHIVED})

#: DELETE .../tasks/{task_id} is only allowed while the task never became (or is
#: no longer) live shared work.
_DELETABLE_STATUSES = frozenset(
    {WorkspaceTaskStatus.PROPOSED, WorkspaceTaskStatus.DECLINED, WorkspaceTaskStatus.ARCHIVED}
)


def _require_member(member: object, *, workspace_id: uuid.UUID) -> None:
    if member is None:
        # IDOR-anti-enumeration -- never 403, see services/checkin_service.py.
        raise NotFoundError(f"workspace {workspace_id} not found")


def _require_task(task: WorkspaceTask | None, *, task_id: uuid.UUID) -> WorkspaceTask:
    if task is None:
        raise NotFoundError(f"task {task_id} not found")
    return task


async def _other_member_user_id(
    db: AsyncSession, *, workspace_id: uuid.UUID, user_id: uuid.UUID
) -> uuid.UUID:
    """Same rationale as services/consent_service.py::_other_member_user_id -- the
    recipient of a FOR_PARTNER_PROPOSED task is always derived from membership,
    never trusted from client input."""
    members = await list_workspace_members(db, workspace_id=workspace_id)
    for member in members:
        if member.user_id != user_id:
            return member.user_id
    raise NotFoundError(f"workspace {workspace_id} has no counterpart member")


async def _record_event(
    db: AsyncSession,
    *,
    task_id: uuid.UUID,
    event_type: TaskAcceptanceEventType,
    actor_user_id: uuid.UUID | None,
) -> None:
    await tasks_repo.create_task_acceptance(
        db, task_id=task_id, event_type=event_type, actor_user_id=actor_user_id
    )


async def _require_milestone_in_workspace(
    db: AsyncSession, *, workspace_id: uuid.UUID, roadmap_milestone_id: uuid.UUID
) -> None:
    """PR-V2-08 -- a `roadmap_milestone_id` link may only ever target a
    `RoadmapMilestone` whose own `RelationshipRoadmap` belongs to the same
    `workspace_id` as the task -- cross-workspace linking is a validation error,
    not an IDOR case (the caller is a legitimate member of `workspace_id`)."""
    milestone = await roadmaps_repo.get_milestone_in_workspace(
        db, milestone_id=roadmap_milestone_id, workspace_id=workspace_id
    )
    if milestone is None:
        raise MilestoneNotInWorkspace(
            f"milestone {roadmap_milestone_id} does not belong to workspace {workspace_id}"
        )


async def create_task(
    db: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
    task_type: TaskType,
    title: str,
    description: str | None,
    due_date: dt.date | None,
    recipient_user_id: uuid.UUID | None,
    roadmap_milestone_id: uuid.UUID | None = None,
) -> WorkspaceTask:
    member = await get_workspace_member(db, workspace_id=workspace_id, user_id=user_id)
    _require_member(member, workspace_id=workspace_id)

    if task_type == TaskType.AVENYTH_SUGGESTED:
        # Never user-creatable -- only services.workspace_task_service.
        # create_avenyth_suggestion (internal function, no route) may create this
        # task_type.
        raise AvenythSuggestedNotUserCreatable(
            "AVENYTH_SUGGESTED tasks cannot be created via this endpoint"
        )

    if roadmap_milestone_id is not None:
        await _require_milestone_in_workspace(
            db, workspace_id=workspace_id, roadmap_milestone_id=roadmap_milestone_id
        )

    if task_type == TaskType.FOR_PARTNER_PROPOSED:
        other_user_id = await _other_member_user_id(db, workspace_id=workspace_id, user_id=user_id)
        # A caller-supplied recipient_user_id is only ever used for spoofing
        # detection -- the true recipient always comes from membership.
        if recipient_user_id is not None and recipient_user_id != other_user_id:
            raise InvalidRecipient("recipient_user_id must be the other workspace member")
        task = await tasks_repo.create_workspace_task(
            db,
            workspace_id=workspace_id,
            task_type=TaskType.FOR_PARTNER_PROPOSED,
            status=WorkspaceTaskStatus.PROPOSED,
            proposer_user_id=user_id,
            recipient_user_id=other_user_id,
            title=title,
            description=description,
            due_date=due_date,
            roadmap_milestone_id=roadmap_milestone_id,
        )
        await _record_event(
            db,
            task_id=task.id,
            event_type=TaskAcceptanceEventType.PROPOSED,
            actor_user_id=user_id,
        )
        return task

    # JOINT_SHARED -- active immediately, no accept step.
    task = await tasks_repo.create_workspace_task(
        db,
        workspace_id=workspace_id,
        task_type=TaskType.JOINT_SHARED,
        status=WorkspaceTaskStatus.ACTIVE,
        proposer_user_id=user_id,
        recipient_user_id=None,
        title=title,
        description=description,
        due_date=due_date,
        roadmap_milestone_id=roadmap_milestone_id,
    )
    await _record_event(
        db, task_id=task.id, event_type=TaskAcceptanceEventType.ACTIVATED, actor_user_id=user_id
    )
    return task


async def create_avenyth_suggestion(
    db: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    title: str,
    description: str | None,
    due_date: dt.date | None,
    source_analysis_id: uuid.UUID,
    prompt_version: str,
    knowledge_version: str,
) -> WorkspaceTask:
    """Internal-only creation path -- no route calls this. Never sets `status` to
    anything but PROPOSED; only an explicit user `accept`/`decline`/PATCH-edit can
    move it further (specs/v2/task-system-spec.md: "never auto-activates")."""
    task = await tasks_repo.create_workspace_task(
        db,
        workspace_id=workspace_id,
        task_type=TaskType.AVENYTH_SUGGESTED,
        status=WorkspaceTaskStatus.PROPOSED,
        proposer_user_id=None,
        recipient_user_id=None,
        title=title,
        description=description,
        due_date=due_date,
        source_analysis_id=source_analysis_id,
        prompt_version=prompt_version,
        knowledge_version=knowledge_version,
    )
    await _record_event(
        db, task_id=task.id, event_type=TaskAcceptanceEventType.PROPOSED, actor_user_id=None
    )
    return task


async def get_task(
    db: AsyncSession, *, workspace_id: uuid.UUID, user_id: uuid.UUID, task_id: uuid.UUID
) -> WorkspaceTask:
    member = await get_workspace_member(db, workspace_id=workspace_id, user_id=user_id)
    _require_member(member, workspace_id=workspace_id)

    task = await tasks_repo.get_workspace_task_for_member(
        db, task_id=task_id, workspace_id=workspace_id, user_id=user_id
    )
    return _require_task(task, task_id=task_id)


async def list_tasks(
    db: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
    status: WorkspaceTaskStatus | None,
    task_type: TaskType | None,
    limit: int,
    offset: int,
) -> list[WorkspaceTask]:
    member = await get_workspace_member(db, workspace_id=workspace_id, user_id=user_id)
    _require_member(member, workspace_id=workspace_id)

    return await tasks_repo.list_workspace_tasks_for_member(
        db,
        workspace_id=workspace_id,
        user_id=user_id,
        status=status,
        task_type=task_type,
        limit=limit,
        offset=offset,
    )


def _can_accept_or_decline(task: WorkspaceTask, *, user_id: uuid.UUID) -> bool:
    if task.task_type == TaskType.FOR_PARTNER_PROPOSED:
        # Self-accept/decline by the proposer is forbidden -- treated as
        # not-found (IDOR-anti-enumeration), same as a non-member.
        return task.recipient_user_id == user_id
    # AVENYTH_SUGGESTED: any ACTIVE workspace member may accept/decline --
    # already gated by get_workspace_member above and the visibility filter in
    # get_workspace_task_for_member. JOINT_SHARED is never PROPOSED (active
    # immediately), so it never reaches this function.
    return task.task_type == TaskType.AVENYTH_SUGGESTED


async def accept_task(
    db: AsyncSession, *, workspace_id: uuid.UUID, user_id: uuid.UUID, task_id: uuid.UUID
) -> WorkspaceTask:
    member = await get_workspace_member(db, workspace_id=workspace_id, user_id=user_id)
    _require_member(member, workspace_id=workspace_id)

    task = await tasks_repo.get_workspace_task_for_member(
        db, task_id=task_id, workspace_id=workspace_id, user_id=user_id
    )
    task = _require_task(task, task_id=task_id)

    if not _can_accept_or_decline(task, user_id=user_id):
        raise NotFoundError(f"task {task_id} not found")

    # Atomic conditional UPDATE, not read-then-write: two concurrent accept/decline
    # requests for the same task must not both pass a Python-side status check
    # before either commits (see repositories/workspace_tasks.py::
    # conditionally_transition_status docstring).
    won = await tasks_repo.conditionally_transition_status(
        db,
        task_id=task.id,
        expected_status=WorkspaceTaskStatus.PROPOSED,
        new_status=WorkspaceTaskStatus.ACTIVE,
    )
    if not won:
        raise TaskTransitionConflict(f"task {task_id} is not in PROPOSED state")
    await db.refresh(task)

    # PROPOSED -> ACCEPTED -> ACTIVE as one step; ACCEPTED is only ever visible
    # as a task_acceptances log entry (specs/v2/task-system-spec.md).
    await _record_event(
        db, task_id=task.id, event_type=TaskAcceptanceEventType.ACCEPTED, actor_user_id=user_id
    )
    await _record_event(
        db, task_id=task.id, event_type=TaskAcceptanceEventType.ACTIVATED, actor_user_id=user_id
    )
    return task


async def decline_task(
    db: AsyncSession, *, workspace_id: uuid.UUID, user_id: uuid.UUID, task_id: uuid.UUID
) -> WorkspaceTask:
    member = await get_workspace_member(db, workspace_id=workspace_id, user_id=user_id)
    _require_member(member, workspace_id=workspace_id)

    task = await tasks_repo.get_workspace_task_for_member(
        db, task_id=task_id, workspace_id=workspace_id, user_id=user_id
    )
    task = _require_task(task, task_id=task_id)

    if not _can_accept_or_decline(task, user_id=user_id):
        raise NotFoundError(f"task {task_id} not found")

    won = await tasks_repo.conditionally_transition_status(
        db,
        task_id=task.id,
        expected_status=WorkspaceTaskStatus.PROPOSED,
        new_status=WorkspaceTaskStatus.DECLINED,
    )
    if not won:
        raise TaskTransitionConflict(f"task {task_id} is not in PROPOSED state")
    await db.refresh(task)

    await _record_event(
        db, task_id=task.id, event_type=TaskAcceptanceEventType.DECLINED, actor_user_id=user_id
    )
    return task


async def patch_task(
    db: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
    task_id: uuid.UUID,
    title: str | None,
    description: str | None,
    due_date: dt.date | None,
    due_date_set: bool,
    description_set: bool,
    status: WorkspaceTaskStatus | None,
    roadmap_milestone_id: uuid.UUID | None = None,
    roadmap_milestone_id_set: bool = False,
) -> WorkspaceTask:
    member = await get_workspace_member(db, workspace_id=workspace_id, user_id=user_id)
    _require_member(member, workspace_id=workspace_id)

    task = await tasks_repo.get_workspace_task_for_member(
        db, task_id=task_id, workspace_id=workspace_id, user_id=user_id
    )
    task = _require_task(task, task_id=task_id)

    updates: dict[str, object] = {}
    if title is not None:
        updates["title"] = title
    if description_set:
        updates["description"] = description
    if due_date_set:
        updates["due_date"] = due_date
    if roadmap_milestone_id_set:
        if roadmap_milestone_id is not None:
            await _require_milestone_in_workspace(
                db, workspace_id=workspace_id, roadmap_milestone_id=roadmap_milestone_id
            )
        updates["roadmap_milestone_id"] = roadmap_milestone_id

    event_type: TaskAcceptanceEventType | None = None
    if status is not None:
        if status not in _PATCHABLE_STATUSES:
            raise TaskTransitionConflict(f"status {status} cannot be set directly via PATCH")
        updates["status"] = status
        # completed_at is server-derived, never client-supplied -- same
        # discipline as PersonalTask (routes/personal_tasks.py).
        if status == WorkspaceTaskStatus.COMPLETED:
            updates["completed_at"] = dt.datetime.now(dt.UTC)
            event_type = TaskAcceptanceEventType.COMPLETED
        else:
            if task.status == WorkspaceTaskStatus.COMPLETED:
                updates["completed_at"] = None
            event_type = TaskAcceptanceEventType.ARCHIVED

    if updates:
        task = await tasks_repo.update_workspace_task(db, task=task, **updates)
    if event_type is not None:
        await _record_event(db, task_id=task.id, event_type=event_type, actor_user_id=user_id)
    return task


async def delete_task(
    db: AsyncSession, *, workspace_id: uuid.UUID, user_id: uuid.UUID, task_id: uuid.UUID
) -> None:
    member = await get_workspace_member(db, workspace_id=workspace_id, user_id=user_id)
    _require_member(member, workspace_id=workspace_id)

    task = await tasks_repo.get_workspace_task_for_member(
        db, task_id=task_id, workspace_id=workspace_id, user_id=user_id
    )
    task = _require_task(task, task_id=task_id)

    if task.status not in _DELETABLE_STATUSES:
        raise TaskNotDeletable(f"task {task_id} in state {task.status} cannot be deleted")

    await tasks_repo.delete_workspace_task(db, task=task)


__all__ = [
    "accept_task",
    "create_avenyth_suggestion",
    "create_task",
    "decline_task",
    "delete_task",
    "get_task",
    "list_tasks",
    "patch_task",
]
