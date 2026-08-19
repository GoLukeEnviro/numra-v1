from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from numra_api.config import Settings
from numra_api.deps import get_current_user, get_db, get_settings_dep, require_csrf
from numra_api.models import User
from numra_api.repositories.people import (
    create_person,
    delete_person,
    get_person,
    list_people,
    update_person,
)
from numra_api.schemas.person import PersonOut, PersonPatchRequest
from numra_api.services.errors import NotFoundError
from numra_api.services.person_service import assert_birth_date_not_in_future
from numra_numerology.models.person import PersonInput

router = APIRouter(prefix="/v1/people", tags=["people"])


def _to_out(person) -> PersonOut:  # type: ignore[no-untyped-def]
    return PersonOut.model_validate(person, from_attributes=True)


@router.get("", response_model=list[PersonOut])
async def list_people_route(
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> list[PersonOut]:
    people = await list_people(db, user_id=user.id)
    return [_to_out(p) for p in people]


@router.post("", response_model=PersonOut, status_code=201, dependencies=[Depends(require_csrf)])
async def create_person_route(
    body: PersonInput,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings_dep),
) -> PersonOut:
    assert_birth_date_not_in_future(body.birth_date, app_timezone=settings.app_timezone)
    person = await create_person(
        db,
        user_id=user.id,
        birth_first_names=body.birth_first_names,
        birth_middle_names=body.birth_middle_names,
        birth_last_name=body.birth_last_name,
        birth_date=body.birth_date,
        birth_time=body.birth_time.model_dump(mode="json") if body.birth_time else None,
        birth_place=body.birth_place.model_dump(mode="json") if body.birth_place else None,
        current_first_names=body.current_first_names,
        current_middle_names=body.current_middle_names,
        current_last_name=body.current_last_name,
        preferred_name=body.preferred_name,
    )
    return _to_out(person)


@router.get("/{person_id}", response_model=PersonOut)
async def get_person_route(
    person_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PersonOut:
    person = await get_person(db, person_id=person_id, user_id=user.id)
    if person is None:
        raise NotFoundError(f"person {person_id} not found")
    return _to_out(person)


@router.patch("/{person_id}", response_model=PersonOut, dependencies=[Depends(require_csrf)])
async def patch_person_route(
    person_id: uuid.UUID,
    body: PersonPatchRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PersonOut:
    person = await get_person(db, person_id=person_id, user_id=user.id)
    if person is None:
        raise NotFoundError(f"person {person_id} not found")
    updates = body.model_dump(exclude_unset=True)
    person = await update_person(db, person=person, **updates)
    return _to_out(person)


@router.delete("/{person_id}", status_code=204, dependencies=[Depends(require_csrf)])
async def delete_person_route(
    person_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    person = await get_person(db, person_id=person_id, user_id=user.id)
    if person is None:
        raise NotFoundError(f"person {person_id} not found")
    await delete_person(db, person=person)
