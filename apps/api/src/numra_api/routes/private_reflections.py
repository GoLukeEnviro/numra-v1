from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from numra_api.deps import get_current_user, get_db, require_csrf
from numra_api.models import PrivateReflection, SharedReflection, User
from numra_api.repositories.people import get_person
from numra_api.repositories.private_reflections import (
    create_private_reflection,
    delete_private_reflection,
    get_private_reflection_for_user,
    list_private_reflections_for_person,
    update_private_reflection,
)
from numra_api.schemas.private_reflection import (
    PrivateReflectionCreateRequest,
    PrivateReflectionOut,
    PrivateReflectionPatchRequest,
)
from numra_api.schemas.shared_reflection import SharedReflectionOut, SharePrivateReflectionRequest
from numra_api.services.errors import NotFoundError
from numra_api.services.feature_flags import require_v2_master
from numra_api.services.shared_reflection_service import share_private_reflection

router = APIRouter(
    prefix="/v1", tags=["private-reflections"], dependencies=[Depends(require_v2_master())]
)


def _to_out(reflection: PrivateReflection) -> PrivateReflectionOut:
    return PrivateReflectionOut.model_validate(reflection, from_attributes=True)


def _shared_out(reflection: SharedReflection) -> SharedReflectionOut:
    return SharedReflectionOut.model_validate(reflection, from_attributes=True)


@router.post(
    "/people/{person_id}/private-reflections",
    response_model=PrivateReflectionOut,
    status_code=201,
    dependencies=[Depends(require_csrf)],
)
async def create_private_reflection_route(
    person_id: uuid.UUID,
    body: PrivateReflectionCreateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db, scope="function"),
) -> PrivateReflectionOut:
    person = await get_person(db, person_id=person_id, user_id=user.id)
    if person is None:
        raise NotFoundError(f"person {person_id} not found")
    reflection = await create_private_reflection(
        db,
        user_id=user.id,
        person_id=person_id,
        entry_date=body.entry_date,
        content=body.content,
    )
    return _to_out(reflection)


@router.get("/people/{person_id}/private-reflections", response_model=list[PrivateReflectionOut])
async def list_private_reflections_route(
    person_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db, scope="function"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[PrivateReflectionOut]:
    person = await get_person(db, person_id=person_id, user_id=user.id)
    if person is None:
        raise NotFoundError(f"person {person_id} not found")
    reflections = await list_private_reflections_for_person(
        db, person_id=person_id, user_id=user.id, limit=limit, offset=offset
    )
    return [_to_out(r) for r in reflections]


@router.get("/private-reflections/{reflection_id}", response_model=PrivateReflectionOut)
async def get_private_reflection_route(
    reflection_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db, scope="function"),
) -> PrivateReflectionOut:
    reflection = await get_private_reflection_for_user(
        db, reflection_id=reflection_id, user_id=user.id
    )
    if reflection is None:
        raise NotFoundError(f"private reflection {reflection_id} not found")
    return _to_out(reflection)


@router.patch(
    "/private-reflections/{reflection_id}",
    response_model=PrivateReflectionOut,
    dependencies=[Depends(require_csrf)],
)
async def patch_private_reflection_route(
    reflection_id: uuid.UUID,
    body: PrivateReflectionPatchRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db, scope="function"),
) -> PrivateReflectionOut:
    reflection = await get_private_reflection_for_user(
        db, reflection_id=reflection_id, user_id=user.id
    )
    if reflection is None:
        raise NotFoundError(f"private reflection {reflection_id} not found")

    set_fields = body.model_fields_set
    updates: dict[str, object] = {}
    if "entry_date" in set_fields:
        updates["entry_date"] = body.entry_date
    if "content" in set_fields:
        updates["content"] = body.content

    reflection = await update_private_reflection(db, reflection=reflection, **updates)
    return _to_out(reflection)


@router.delete(
    "/private-reflections/{reflection_id}", status_code=204, dependencies=[Depends(require_csrf)]
)
async def delete_private_reflection_route(
    reflection_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db, scope="function"),
) -> None:
    reflection = await get_private_reflection_for_user(
        db, reflection_id=reflection_id, user_id=user.id
    )
    if reflection is None:
        raise NotFoundError(f"private reflection {reflection_id} not found")
    await delete_private_reflection(db, reflection=reflection)


@router.post(
    "/private-reflections/{reflection_id}/share",
    response_model=SharedReflectionOut,
    status_code=201,
    dependencies=[Depends(require_csrf)],
)
async def share_private_reflection_route(
    reflection_id: uuid.UUID,
    body: SharePrivateReflectionRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db, scope="function"),
) -> SharedReflectionOut:
    reflection = await share_private_reflection(
        db, reflection_id=reflection_id, user_id=user.id, workspace_id=body.workspace_id
    )
    return _shared_out(reflection)
