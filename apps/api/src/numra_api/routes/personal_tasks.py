from __future__ import annotations

import datetime as dt
import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from numra_api.deps import get_current_user, get_db, require_csrf
from numra_api.models import PersonalTask, User
from numra_api.models.enums import PersonalTaskStatus
from numra_api.repositories.people import get_person
from numra_api.repositories.personal_tasks import (
    create_personal_task,
    delete_personal_task,
    get_personal_task_for_user,
    list_personal_tasks_for_person,
    update_personal_task,
)
from numra_api.schemas.personal_task import (
    PersonalTaskCreateRequest,
    PersonalTaskOut,
    PersonalTaskPatchRequest,
)
from numra_api.services.errors import NotFoundError

router = APIRouter(prefix="/v1", tags=["personal-tasks"])


def _to_out(task: PersonalTask) -> PersonalTaskOut:
    return PersonalTaskOut.model_validate(task, from_attributes=True)


@router.post(
    "/people/{person_id}/personal-tasks",
    response_model=PersonalTaskOut,
    status_code=201,
    dependencies=[Depends(require_csrf)],
)
async def create_personal_task_route(
    person_id: uuid.UUID,
    body: PersonalTaskCreateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PersonalTaskOut:
    person = await get_person(db, person_id=person_id, user_id=user.id)
    if person is None:
        raise NotFoundError(f"person {person_id} not found")
    task = await create_personal_task(
        db,
        user_id=user.id,
        person_id=person_id,
        title=body.title,
        description=body.description,
        due_date=body.due_date,
    )
    return _to_out(task)


@router.get("/people/{person_id}/personal-tasks", response_model=list[PersonalTaskOut])
async def list_personal_tasks_route(
    person_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    status: PersonalTaskStatus | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[PersonalTaskOut]:
    person = await get_person(db, person_id=person_id, user_id=user.id)
    if person is None:
        raise NotFoundError(f"person {person_id} not found")
    tasks = await list_personal_tasks_for_person(
        db, person_id=person_id, user_id=user.id, status=status, limit=limit, offset=offset
    )
    return [_to_out(t) for t in tasks]


@router.get("/personal-tasks/{task_id}", response_model=PersonalTaskOut)
async def get_personal_task_route(
    task_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PersonalTaskOut:
    task = await get_personal_task_for_user(db, task_id=task_id, user_id=user.id)
    if task is None:
        raise NotFoundError(f"personal task {task_id} not found")
    return _to_out(task)


@router.patch(
    "/personal-tasks/{task_id}",
    response_model=PersonalTaskOut,
    dependencies=[Depends(require_csrf)],
)
async def patch_personal_task_route(
    task_id: uuid.UUID,
    body: PersonalTaskPatchRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PersonalTaskOut:
    task = await get_personal_task_for_user(db, task_id=task_id, user_id=user.id)
    if task is None:
        raise NotFoundError(f"personal task {task_id} not found")

    set_fields = body.model_fields_set
    updates: dict[str, object] = {}
    if "title" in set_fields:
        updates["title"] = body.title
    if "description" in set_fields:
        updates["description"] = body.description
    if "due_date" in set_fields:
        updates["due_date"] = body.due_date
    if "status" in set_fields:
        updates["status"] = body.status
        # completed_at is server-derived, never client-supplied: set on the
        # ACTIVE/ARCHIVED -> COMPLETED transition, cleared on any transition back out
        # of COMPLETED (e.g. reopened to ACTIVE, or archived directly).
        if body.status == PersonalTaskStatus.COMPLETED:
            updates["completed_at"] = dt.datetime.now(dt.UTC)
        elif task.status == PersonalTaskStatus.COMPLETED:
            updates["completed_at"] = None

    task = await update_personal_task(db, task=task, **updates)
    return _to_out(task)


@router.delete("/personal-tasks/{task_id}", status_code=204, dependencies=[Depends(require_csrf)])
async def delete_personal_task_route(
    task_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    task = await get_personal_task_for_user(db, task_id=task_id, user_id=user.id)
    if task is None:
        raise NotFoundError(f"personal task {task_id} not found")
    await delete_personal_task(db, task=task)
