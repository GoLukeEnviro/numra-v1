"""specs/v2/task-system-spec.md -- Shared Task System (PR-V2-07). Every route
gates on `get_workspace_member` first (inside the service layer), returning 404
(never 403) for a non-member -- same IDOR pattern as routes/checkins.py /
routes/consent.py. No admin endpoint here, no AVENYTH_SUGGESTED user-facing
create route (see services/workspace_task_service.py::create_avenyth_suggestion
docstring)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from numra_api.deps import get_current_user, get_db, require_csrf
from numra_api.models import User, WorkspaceTask
from numra_api.models.enums import TaskType, WorkspaceTaskStatus
from numra_api.schemas.workspace_task import (
    WorkspaceTaskCreateRequest,
    WorkspaceTaskOut,
    WorkspaceTaskPatchRequest,
)
from numra_api.services.workspace_task_service import (
    accept_task,
    create_task,
    decline_task,
    delete_task,
    get_task,
    list_tasks,
    patch_task,
)

router = APIRouter(prefix="/v1/workspaces/{workspace_id}", tags=["workspace-tasks"])


def _to_out(task: WorkspaceTask) -> WorkspaceTaskOut:
    return WorkspaceTaskOut.model_validate(task, from_attributes=True)


@router.post(
    "/tasks", response_model=WorkspaceTaskOut, status_code=201, dependencies=[Depends(require_csrf)]
)
async def create_task_route(
    workspace_id: uuid.UUID,
    body: WorkspaceTaskCreateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WorkspaceTaskOut:
    task = await create_task(
        db,
        workspace_id=workspace_id,
        user_id=user.id,
        task_type=body.task_type,
        title=body.title,
        description=body.description,
        due_date=body.due_date,
        recipient_user_id=body.recipient_user_id,
    )
    return _to_out(task)


@router.get("/tasks", response_model=list[WorkspaceTaskOut])
async def list_tasks_route(
    workspace_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    status: WorkspaceTaskStatus | None = Query(default=None),
    task_type: TaskType | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[WorkspaceTaskOut]:
    tasks = await list_tasks(
        db,
        workspace_id=workspace_id,
        user_id=user.id,
        status=status,
        task_type=task_type,
        limit=limit,
        offset=offset,
    )
    return [_to_out(t) for t in tasks]


@router.get("/tasks/{task_id}", response_model=WorkspaceTaskOut)
async def get_task_route(
    workspace_id: uuid.UUID,
    task_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WorkspaceTaskOut:
    task = await get_task(db, workspace_id=workspace_id, user_id=user.id, task_id=task_id)
    return _to_out(task)


@router.post(
    "/tasks/{task_id}/accept",
    response_model=WorkspaceTaskOut,
    dependencies=[Depends(require_csrf)],
)
async def accept_task_route(
    workspace_id: uuid.UUID,
    task_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WorkspaceTaskOut:
    task = await accept_task(db, workspace_id=workspace_id, user_id=user.id, task_id=task_id)
    return _to_out(task)


@router.post(
    "/tasks/{task_id}/decline",
    response_model=WorkspaceTaskOut,
    dependencies=[Depends(require_csrf)],
)
async def decline_task_route(
    workspace_id: uuid.UUID,
    task_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WorkspaceTaskOut:
    task = await decline_task(db, workspace_id=workspace_id, user_id=user.id, task_id=task_id)
    return _to_out(task)


@router.patch(
    "/tasks/{task_id}", response_model=WorkspaceTaskOut, dependencies=[Depends(require_csrf)]
)
async def patch_task_route(
    workspace_id: uuid.UUID,
    task_id: uuid.UUID,
    body: WorkspaceTaskPatchRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WorkspaceTaskOut:
    set_fields = body.model_fields_set
    task = await patch_task(
        db,
        workspace_id=workspace_id,
        user_id=user.id,
        task_id=task_id,
        title=body.title if "title" in set_fields else None,
        description=body.description,
        description_set="description" in set_fields,
        due_date=body.due_date,
        due_date_set="due_date" in set_fields,
        status=body.status,
    )
    return _to_out(task)


@router.delete("/tasks/{task_id}", status_code=204, dependencies=[Depends(require_csrf)])
async def delete_task_route(
    workspace_id: uuid.UUID,
    task_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    await delete_task(db, workspace_id=workspace_id, user_id=user.id, task_id=task_id)
