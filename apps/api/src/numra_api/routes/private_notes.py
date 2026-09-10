from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from numra_api.deps import get_current_user, get_db, require_csrf
from numra_api.models import PrivateNote, User
from numra_api.repositories.people import get_person
from numra_api.repositories.private_notes import (
    create_private_note,
    delete_private_note,
    get_private_note_for_user,
    list_private_notes_for_person,
    update_private_note,
)
from numra_api.schemas.private_note import (
    PrivateNoteCreateRequest,
    PrivateNoteOut,
    PrivateNotePatchRequest,
)
from numra_api.services.errors import NotFoundError
from numra_api.services.feature_flags import require_v2_master

router = APIRouter(
    prefix="/v1", tags=["private-notes"], dependencies=[Depends(require_v2_master())]
)


def _to_out(note: PrivateNote) -> PrivateNoteOut:
    return PrivateNoteOut.model_validate(note, from_attributes=True)


@router.post(
    "/people/{person_id}/private-notes",
    response_model=PrivateNoteOut,
    status_code=201,
    dependencies=[Depends(require_csrf)],
)
async def create_private_note_route(
    person_id: uuid.UUID,
    body: PrivateNoteCreateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db, scope="function"),
) -> PrivateNoteOut:
    person = await get_person(db, person_id=person_id, user_id=user.id)
    if person is None:
        raise NotFoundError(f"person {person_id} not found")
    note = await create_private_note(
        db, user_id=user.id, person_id=person_id, title=body.title, content=body.content
    )
    return _to_out(note)


@router.get("/people/{person_id}/private-notes", response_model=list[PrivateNoteOut])
async def list_private_notes_route(
    person_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db, scope="function"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[PrivateNoteOut]:
    person = await get_person(db, person_id=person_id, user_id=user.id)
    if person is None:
        raise NotFoundError(f"person {person_id} not found")
    notes = await list_private_notes_for_person(
        db, person_id=person_id, user_id=user.id, limit=limit, offset=offset
    )
    return [_to_out(n) for n in notes]


@router.get("/private-notes/{note_id}", response_model=PrivateNoteOut)
async def get_private_note_route(
    note_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db, scope="function"),
) -> PrivateNoteOut:
    note = await get_private_note_for_user(db, note_id=note_id, user_id=user.id)
    if note is None:
        raise NotFoundError(f"private note {note_id} not found")
    return _to_out(note)


@router.patch(
    "/private-notes/{note_id}", response_model=PrivateNoteOut, dependencies=[Depends(require_csrf)]
)
async def patch_private_note_route(
    note_id: uuid.UUID,
    body: PrivateNotePatchRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db, scope="function"),
) -> PrivateNoteOut:
    note = await get_private_note_for_user(db, note_id=note_id, user_id=user.id)
    if note is None:
        raise NotFoundError(f"private note {note_id} not found")

    set_fields = body.model_fields_set
    updates: dict[str, object] = {}
    if "title" in set_fields:
        updates["title"] = body.title
    if "content" in set_fields:
        updates["content"] = body.content

    note = await update_private_note(db, note=note, **updates)
    return _to_out(note)


@router.delete("/private-notes/{note_id}", status_code=204, dependencies=[Depends(require_csrf)])
async def delete_private_note_route(
    note_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db, scope="function"),
) -> None:
    note = await get_private_note_for_user(db, note_id=note_id, user_id=user.id)
    if note is None:
        raise NotFoundError(f"private note {note_id} not found")
    await delete_private_note(db, note=note)
