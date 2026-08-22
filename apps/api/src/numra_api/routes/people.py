from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from numra_api.config import Settings
from numra_api.deps import get_current_user, get_db, get_settings_dep, require_csrf
from numra_api.models import NameIdentity, User
from numra_api.repositories.identities import list_name_identities_for_person, sync_identity_history
from numra_api.repositories.people import (
    create_person,
    delete_person,
    get_person,
    list_people,
    update_person,
)
from numra_api.schemas.person import NameIdentityOut, PersonOut, PersonPatchRequest
from numra_api.services.errors import NotFoundError
from numra_api.services.person_service import assert_birth_date_not_in_future
from numra_numerology.models.person import PersonInput

router = APIRouter(prefix="/v1/people", tags=["people"])


def _to_out(person) -> PersonOut:  # type: ignore[no-untyped-def]
    return PersonOut.model_validate(person, from_attributes=True)


def _identity_to_out(identity: NameIdentity) -> NameIdentityOut:
    return NameIdentityOut(
        id=identity.id,
        kind=identity.kind,
        first_names=identity.first_names,
        middle_names=identity.middle_names,
        last_name=identity.last_name,
        valid_from=identity.valid_from,
        recorded_at=identity.created_at,
    )


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
    await sync_identity_history(db, person=person)
    return _to_out(person)


@router.get("/{person_id}/identities", response_model=list[NameIdentityOut])
async def list_identities_route(
    person_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[NameIdentityOut]:
    person = await get_person(db, person_id=person_id, user_id=user.id)
    if person is None:
        raise NotFoundError(f"person {person_id} not found")
    identities = await list_name_identities_for_person(db, person_id=person_id, user_id=user.id)
    return [_identity_to_out(i) for i in identities]


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
    settings: Settings = Depends(get_settings_dep),
) -> PersonOut:
    person = await get_person(db, person_id=person_id, user_id=user.id)
    if person is None:
        raise NotFoundError(f"person {person_id} not found")

    if body.birth_date is not None:
        assert_birth_date_not_in_future(body.birth_date, app_timezone=settings.app_timezone)

    # Built field-by-field (not a blanket body.model_dump()) so BirthTime/BirthPlace
    # serialize to JSON-safe dicts for the JSONB columns exactly like create_person
    # does, while birth_date stays a native `date` for the Date column -- a single
    # model_dump(mode="json") would turn birth_date into a string too, which the
    # Date column does not accept. Editing a Person NEVER touches any existing
    # Calculation row (those are immutable snapshots) -- only a future calculation
    # reflects the edit.
    set_fields = body.model_fields_set
    updates: dict[str, object] = {}
    if "birth_first_names" in set_fields:
        updates["birth_first_names"] = body.birth_first_names
    if "birth_middle_names" in set_fields:
        updates["birth_middle_names"] = body.birth_middle_names
    if "birth_last_name" in set_fields:
        updates["birth_last_name"] = body.birth_last_name
    if "birth_date" in set_fields:
        updates["birth_date"] = body.birth_date
    if "birth_time" in set_fields:
        updates["birth_time"] = body.birth_time.model_dump(mode="json") if body.birth_time else None
    if "birth_place" in set_fields:
        updates["birth_place"] = (
            body.birth_place.model_dump(mode="json") if body.birth_place else None
        )
    if "current_first_names" in set_fields:
        updates["current_first_names"] = body.current_first_names
    if "current_middle_names" in set_fields:
        updates["current_middle_names"] = body.current_middle_names
    if "current_last_name" in set_fields:
        updates["current_last_name"] = body.current_last_name
    if "preferred_name" in set_fields:
        updates["preferred_name"] = body.preferred_name

    person = await update_person(db, person=person, **updates)
    await sync_identity_history(db, person=person)
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
