"""V1.5 Epic C: a truthful, append-only record of the names Numra has held for a
person. Never rewritten, never backfilled with a guessed date -- `created_at` (when
this row was actually recorded) and `valid_from` (only ever set from an
already-known fact, such as the birth date itself, never invented for current/
preferred names) are kept strictly separate. See `NameIdentity` in
`models/tables.py`.
"""

from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from numra_api.models import NameIdentity, Person
from numra_api.models.enums import NameIdentityKind


async def list_name_identities_for_person(
    db: AsyncSession, *, person_id: uuid.UUID, user_id: uuid.UUID
) -> list[NameIdentity]:
    stmt = (
        select(NameIdentity)
        .join(Person, Person.id == NameIdentity.person_id)
        .where(NameIdentity.person_id == person_id, Person.user_id == user_id)
        .order_by(NameIdentity.created_at.desc())
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def _append_if_changed(
    db: AsyncSession,
    *,
    existing_latest: NameIdentity | None,
    person_id: uuid.UUID,
    kind: NameIdentityKind,
    first_names: str,
    middle_names: str | None,
    last_name: str,
    valid_from: dt.date | None,
) -> None:
    if (
        existing_latest is not None
        and existing_latest.first_names == first_names
        and existing_latest.middle_names == middle_names
        and existing_latest.last_name == last_name
    ):
        return  # Nothing actually changed for this kind -- no duplicate row.
    db.add(
        NameIdentity(
            person_id=person_id,
            kind=kind,
            first_names=first_names,
            middle_names=middle_names,
            last_name=last_name,
            valid_from=valid_from,
        )
    )


async def sync_identity_history(db: AsyncSession, *, person: Person) -> None:
    """Called after a Person is created or patched: appends a new NameIdentity row
    for each kind (birth/current/preferred) whose recorded name actually differs
    from the latest entry of that kind -- a no-op for kinds nothing changed on.
    Idempotent to call after every write; never mutates or removes an existing row.

    `preferred_name` has no first/middle/last split -- it is recorded with the whole
    value in `first_names` and an empty `last_name`, never inferred from the birth or
    current name (a preferred nickname is not a full legal identity)."""
    existing = await list_name_identities_for_person(
        db, person_id=person.id, user_id=person.user_id
    )
    latest_by_kind = {
        kind: next((e for e in existing if e.kind == kind), None) for kind in NameIdentityKind
    }

    # Birth identity: valid_from = birth_date is a genuinely known fact (not a guess),
    # unlike current/preferred names where no effective date is ever known.
    await _append_if_changed(
        db,
        existing_latest=latest_by_kind[NameIdentityKind.BIRTH],
        person_id=person.id,
        kind=NameIdentityKind.BIRTH,
        first_names=person.birth_first_names,
        middle_names=person.birth_middle_names,
        last_name=person.birth_last_name,
        valid_from=person.birth_date,
    )

    if person.current_first_names or person.current_last_name:
        await _append_if_changed(
            db,
            existing_latest=latest_by_kind[NameIdentityKind.CURRENT],
            person_id=person.id,
            kind=NameIdentityKind.CURRENT,
            first_names=person.current_first_names or "",
            middle_names=person.current_middle_names,
            last_name=person.current_last_name or "",
            valid_from=None,
        )

    if person.preferred_name:
        await _append_if_changed(
            db,
            existing_latest=latest_by_kind[NameIdentityKind.PREFERRED],
            person_id=person.id,
            kind=NameIdentityKind.PREFERRED,
            first_names=person.preferred_name,
            middle_names=None,
            last_name="",
            valid_from=None,
        )

    await db.flush()
