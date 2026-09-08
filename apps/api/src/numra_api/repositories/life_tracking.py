from __future__ import annotations

import datetime as dt
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from numra_api.models import (
    CustomMetricDefinition,
    LifeTrackingEntry,
    LifeTrackingMetricValue,
    Person,
)


async def create_life_tracking_entry(
    db: AsyncSession, *, user_id: uuid.UUID, person_id: uuid.UUID, **fields: Any
) -> LifeTrackingEntry:
    entry = LifeTrackingEntry(user_id=user_id, person_id=person_id, **fields)
    db.add(entry)
    await db.flush()
    return entry


async def get_life_tracking_entry_for_user(
    db: AsyncSession, *, entry_id: uuid.UUID, user_id: uuid.UUID
) -> LifeTrackingEntry | None:
    stmt = select(LifeTrackingEntry).where(
        LifeTrackingEntry.id == entry_id, LifeTrackingEntry.user_id == user_id
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def list_life_tracking_entries_for_person(
    db: AsyncSession,
    *,
    person_id: uuid.UUID,
    user_id: uuid.UUID,
    date_from: dt.date | None = None,
    date_to: dt.date | None = None,
    limit: int | None = None,
    offset: int | None = None,
) -> list[LifeTrackingEntry]:
    """Ohne ``limit``/``offset`` die vollstaendige Historie -- genau das braucht
    ``evidence_service.py`` fuer die Korrelationsrechnung; eine gekappte Liste wuerde
    dort still eine falsche ``sample_size`` erzeugen."""
    stmt = select(LifeTrackingEntry).where(
        LifeTrackingEntry.person_id == person_id, LifeTrackingEntry.user_id == user_id
    )
    if date_from is not None:
        stmt = stmt.where(LifeTrackingEntry.entry_date >= date_from)
    if date_to is not None:
        stmt = stmt.where(LifeTrackingEntry.entry_date <= date_to)
    stmt = stmt.order_by(LifeTrackingEntry.entry_date.desc())
    if limit is not None:
        stmt = stmt.limit(limit)
    if offset is not None:
        stmt = stmt.offset(offset)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def update_life_tracking_entry(
    db: AsyncSession, *, entry: LifeTrackingEntry, **fields: Any
) -> LifeTrackingEntry:
    for key, value in fields.items():
        setattr(entry, key, value)
    await db.flush()
    await db.refresh(entry)
    return entry


async def replace_custom_metric_values(
    db: AsyncSession, *, entry: LifeTrackingEntry, values: dict[str, int]
) -> LifeTrackingEntry:
    """Ersetzt die Custom-Werte eines Eintrags vollstaendig. ``delete-orphan`` auf
    ``LifeTrackingEntry.metric_values`` raeumt die abgehaengten Zeilen ab -- deshalb
    braucht es hier kein explizites DELETE.

    Das ``refresh`` mit explizitem Attributnamen ist unter ``AsyncSession`` Pflicht:
    die Zuweisung an eine Collection laedt zuerst den bisherigen Inhalt, um das
    Delete-Orphan-Delta zu bilden -- ein impliziter Lazy Load an dieser Stelle
    scheitert mit ``MissingGreenlet``. Seit SQLAlchemy 2.0.4 loest ``refresh`` einen
    benannten Relationship-Load sofort und asynchron aus."""
    await db.refresh(entry, ["metric_values"])
    entry.metric_values = [
        LifeTrackingMetricValue(metric_key=metric_key, value=value)
        for metric_key, value in sorted(values.items())
    ]
    await db.flush()
    await db.refresh(entry)
    return entry


async def delete_life_tracking_entry(db: AsyncSession, *, entry: LifeTrackingEntry) -> None:
    await db.delete(entry)


async def create_custom_metric_definition(
    db: AsyncSession, *, person_id: uuid.UUID, **fields: Any
) -> CustomMetricDefinition:
    definition = CustomMetricDefinition(person_id=person_id, **fields)
    db.add(definition)
    await db.flush()
    return definition


async def get_custom_metric_definition_by_key(
    db: AsyncSession, *, person_id: uuid.UUID, metric_key: str
) -> CustomMetricDefinition | None:
    """Findet auch bereits stillgelegte Definitionen -- ``metric_key`` ist unveraender-
    lich, eine Neuvergabe muss also selbst dann scheitern, wenn die alte Definition
    ``active=False`` ist (gleiche Regel wie ``CheckinDimension.semantic_key``)."""
    stmt = select(CustomMetricDefinition).where(
        CustomMetricDefinition.person_id == person_id,
        CustomMetricDefinition.metric_key == metric_key,
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def get_custom_metric_definition_for_user(
    db: AsyncSession, *, definition_id: uuid.UUID, user_id: uuid.UUID
) -> CustomMetricDefinition | None:
    """IDOR-Grenze ueber den Join auf ``people.user_id`` -- ``CustomMetricDefinition``
    traegt selbst kein ``user_id`` (sie ist Person-, nicht User-Eigentum)."""
    stmt = (
        select(CustomMetricDefinition)
        .join(Person, Person.id == CustomMetricDefinition.person_id)
        .where(CustomMetricDefinition.id == definition_id, Person.user_id == user_id)
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def list_custom_metric_definitions_for_person(
    db: AsyncSession, *, person_id: uuid.UUID
) -> list[CustomMetricDefinition]:
    stmt = (
        select(CustomMetricDefinition)
        .where(CustomMetricDefinition.person_id == person_id)
        .order_by(CustomMetricDefinition.created_at.asc())
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def update_custom_metric_definition(
    db: AsyncSession, *, definition: CustomMetricDefinition, **fields: Any
) -> CustomMetricDefinition:
    for key, value in fields.items():
        setattr(definition, key, value)
    await db.flush()
    await db.refresh(definition)
    return definition
