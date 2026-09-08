"""PR-V2-07 -- specs/v2/task-system-spec.md. `get_workspace_task_for_member`/
`list_workspace_tasks_for_member` both apply the same server-side visibility
predicate (see `_visible_to_member`), never client-steerable: a
`FOR_PARTNER_PROPOSED` row is only visible to its proposer/recipient,
`JOINT_SHARED`/`AVENYTH_SUGGESTED` rows are visible to any ACTIVE member of the
workspace. Callers must still gate on `get_workspace_member` first (IDOR
anti-enumeration, see services/workspace_task_service.py) -- this predicate is a
second, belt-and-suspenders filter, same discipline as
repositories/checkins.py.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import ColumnElement, and_, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from numra_api.models import TaskAcceptance, WorkspaceTask
from numra_api.models.enums import TaskAcceptanceEventType, TaskType, WorkspaceTaskStatus


def _visible_to_member(user_id: uuid.UUID) -> ColumnElement[bool]:
    return or_(
        and_(
            WorkspaceTask.task_type == TaskType.FOR_PARTNER_PROPOSED,
            or_(
                WorkspaceTask.proposer_user_id == user_id,
                WorkspaceTask.recipient_user_id == user_id,
            ),
        ),
        WorkspaceTask.task_type.in_([TaskType.JOINT_SHARED, TaskType.AVENYTH_SUGGESTED]),
    )


async def create_workspace_task(db: AsyncSession, **fields: Any) -> WorkspaceTask:
    task = WorkspaceTask(**fields)
    db.add(task)
    await db.flush()
    return task


async def get_workspace_task_for_member(
    db: AsyncSession, *, task_id: uuid.UUID, workspace_id: uuid.UUID, user_id: uuid.UUID
) -> WorkspaceTask | None:
    stmt = select(WorkspaceTask).where(
        WorkspaceTask.id == task_id,
        WorkspaceTask.workspace_id == workspace_id,
        _visible_to_member(user_id),
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def list_workspace_tasks_for_member(
    db: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
    status: WorkspaceTaskStatus | None,
    task_type: TaskType | None,
    limit: int,
    offset: int,
) -> list[WorkspaceTask]:
    stmt = select(WorkspaceTask).where(
        WorkspaceTask.workspace_id == workspace_id, _visible_to_member(user_id)
    )
    if status is not None:
        stmt = stmt.where(WorkspaceTask.status == status)
    if task_type is not None:
        stmt = stmt.where(WorkspaceTask.task_type == task_type)
    stmt = stmt.order_by(WorkspaceTask.created_at.desc()).limit(limit).offset(offset)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def update_workspace_task(
    db: AsyncSession, *, task: WorkspaceTask, **fields: Any
) -> WorkspaceTask:
    for key, value in fields.items():
        setattr(task, key, value)
    await db.flush()
    await db.refresh(task)
    return task


async def conditionally_transition_status(
    db: AsyncSession,
    *,
    task_id: uuid.UUID,
    expected_status: Any,
    new_status: Any,
) -> bool:
    """Atomic `UPDATE ... WHERE id=? AND status=?` -- the actual TOCTOU-safety
    guarantee for accept/decline (a plain read-then-`setattr`-then-flush is
    racy: two concurrent requests can both pass the Python-side status check
    before either commits). Returns whether this call won the transition;
    `False` means someone else already moved the task out of
    `expected_status` and the caller must treat it as a conflict, not retry
    silently -- same discipline as repositories/checkins.py's partial unique
    index for the analogous first-submission race."""
    stmt = (
        update(WorkspaceTask)
        .where(WorkspaceTask.id == task_id, WorkspaceTask.status == expected_status)
        .values(status=new_status)
        .returning(WorkspaceTask.id)
    )
    result = await db.execute(stmt)
    await db.flush()
    return result.scalar_one_or_none() is not None


async def delete_workspace_task(db: AsyncSession, *, task: WorkspaceTask) -> None:
    await db.delete(task)


async def create_task_acceptance(
    db: AsyncSession,
    *,
    task_id: uuid.UUID,
    event_type: TaskAcceptanceEventType,
    actor_user_id: uuid.UUID | None,
) -> TaskAcceptance:
    event = TaskAcceptance(task_id=task_id, event_type=event_type, actor_user_id=actor_user_id)
    db.add(event)
    await db.flush()
    return event
