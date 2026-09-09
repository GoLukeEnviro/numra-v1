"""PR-V2-11 -- Life-Tracking-Eintraege und Custom-Metrik-Definitionen
(specs/v2/evidence-policy.md "Life Tracking data model").

IDOR-Gate wie ueberall in diesem Repo: jede Person-Route laedt zuerst
`get_person(db, person_id=..., user_id=user.id)` und antwortet mit 404 statt 403,
Einzelressourcen-Routen laden ueber `..._for_user`. Die Validierung der
Custom-Metriken lebt hier statt in einem eigenen Service, weil sie ausschliesslich
Request-Validierung ist -- es gibt keine Orchestrierung ueber mehrere Repositories.
"""

from __future__ import annotations

import datetime as dt
import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from numra_api.deps import get_current_user, get_db, require_csrf
from numra_api.models import CustomMetricDefinition, LifeTrackingEntry, Person, User
from numra_api.repositories.life_tracking import (
    create_custom_metric_definition,
    create_life_tracking_entry,
    delete_life_tracking_entry,
    get_custom_metric_definition_by_key,
    get_custom_metric_definition_for_user,
    get_life_tracking_entry_for_user,
    list_custom_metric_definitions_for_person,
    list_life_tracking_entries_for_person,
    replace_custom_metric_values,
    update_custom_metric_definition,
    update_life_tracking_entry,
)
from numra_api.repositories.people import get_person
from numra_api.schemas.life_tracking import (
    CustomMetricDefinitionCreateRequest,
    CustomMetricDefinitionOut,
    CustomMetricDefinitionPatchRequest,
    LifeTrackingEntryCreateRequest,
    LifeTrackingEntryOut,
    LifeTrackingEntryPatchRequest,
)
from numra_api.services.errors import (
    MetricKeyImmutable,
    MetricValueOutOfScale,
    NotFoundError,
)
from numra_api.services.feature_flags import require_v2_phase

router = APIRouter(
    prefix="/v1",
    tags=["life-tracking"],
    dependencies=[Depends(require_v2_phase("evidence_layer"))],
)

#: Felder, die beim PATCH direkt auf den Eintrag durchgereicht werden.
#: `custom_metrics` ist bewusst nicht dabei -- es landet in einer eigenen Tabelle.
_PATCHABLE_ENTRY_FIELDS = (
    "entry_date",
    "calculation_id",
    "mood",
    "energy",
    "sleep",
    "stress",
    "focus",
    "note",
)


def _to_entry_out(entry: LifeTrackingEntry) -> LifeTrackingEntryOut:
    return LifeTrackingEntryOut(
        id=entry.id,
        person_id=entry.person_id,
        entry_date=entry.entry_date,
        calculation_id=entry.calculation_id,
        mood=entry.mood,
        energy=entry.energy,
        sleep=entry.sleep,
        stress=entry.stress,
        focus=entry.focus,
        note=entry.note,
        custom_metrics={value.metric_key: value.value for value in entry.metric_values},
        created_at=entry.created_at,
        updated_at=entry.updated_at,
    )


def _to_definition_out(definition: CustomMetricDefinition) -> CustomMetricDefinitionOut:
    return CustomMetricDefinitionOut.model_validate(definition, from_attributes=True)


async def _require_person(db: AsyncSession, *, person_id: uuid.UUID, user_id: uuid.UUID) -> Person:
    person = await get_person(db, person_id=person_id, user_id=user_id)
    if person is None:
        raise NotFoundError(f"person {person_id} not found")
    return person


async def _validate_custom_metrics(
    db: AsyncSession, *, person_id: uuid.UUID, custom_metrics: dict[str, int]
) -> None:
    """Jeder Key muss eine AKTIVE `CustomMetricDefinition` der Person sein, und der
    Wert muss in deren eigener Skala liegen. Eine stillgelegte Definition nimmt
    keine neuen Werte mehr an -- ihre historischen Werte bleiben aber lesbar und
    auswertbar."""
    for metric_key, value in custom_metrics.items():
        definition = await get_custom_metric_definition_by_key(
            db, person_id=person_id, metric_key=metric_key
        )
        if definition is None or not definition.active:
            raise NotFoundError(
                f"active custom metric definition {metric_key!r} not found for person {person_id}"
            )
        if not definition.scale_min <= value <= definition.scale_max:
            raise MetricValueOutOfScale(
                f"value {value} for metric {metric_key!r} is outside its scale "
                f"{definition.scale_min}..{definition.scale_max}"
            )


@router.post(
    "/people/{person_id}/life-tracking-entries",
    response_model=LifeTrackingEntryOut,
    status_code=201,
    dependencies=[Depends(require_csrf)],
)
async def create_life_tracking_entry_route(
    person_id: uuid.UUID,
    body: LifeTrackingEntryCreateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> LifeTrackingEntryOut:
    await _require_person(db, person_id=person_id, user_id=user.id)
    await _validate_custom_metrics(db, person_id=person_id, custom_metrics=body.custom_metrics)

    entry = await create_life_tracking_entry(
        db,
        user_id=user.id,
        person_id=person_id,
        entry_date=body.entry_date,
        calculation_id=body.calculation_id,
        mood=body.mood,
        energy=body.energy,
        sleep=body.sleep,
        stress=body.stress,
        focus=body.focus,
        note=body.note,
    )
    entry = await replace_custom_metric_values(db, entry=entry, values=body.custom_metrics)
    return _to_entry_out(entry)


@router.get("/people/{person_id}/life-tracking-entries", response_model=list[LifeTrackingEntryOut])
async def list_life_tracking_entries_route(
    person_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    date_from: dt.date | None = Query(default=None, alias="from"),
    date_to: dt.date | None = Query(default=None, alias="to"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[LifeTrackingEntryOut]:
    await _require_person(db, person_id=person_id, user_id=user.id)
    entries = await list_life_tracking_entries_for_person(
        db,
        person_id=person_id,
        user_id=user.id,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
        offset=offset,
    )
    return [_to_entry_out(entry) for entry in entries]


@router.get("/life-tracking-entries/{entry_id}", response_model=LifeTrackingEntryOut)
async def get_life_tracking_entry_route(
    entry_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> LifeTrackingEntryOut:
    entry = await get_life_tracking_entry_for_user(db, entry_id=entry_id, user_id=user.id)
    if entry is None:
        raise NotFoundError(f"life tracking entry {entry_id} not found")
    return _to_entry_out(entry)


@router.patch(
    "/life-tracking-entries/{entry_id}",
    response_model=LifeTrackingEntryOut,
    dependencies=[Depends(require_csrf)],
)
async def patch_life_tracking_entry_route(
    entry_id: uuid.UUID,
    body: LifeTrackingEntryPatchRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> LifeTrackingEntryOut:
    entry = await get_life_tracking_entry_for_user(db, entry_id=entry_id, user_id=user.id)
    if entry is None:
        raise NotFoundError(f"life tracking entry {entry_id} not found")

    set_fields = body.model_fields_set
    updates = {
        field: getattr(body, field) for field in _PATCHABLE_ENTRY_FIELDS if field in set_fields
    }
    if updates:
        entry = await update_life_tracking_entry(db, entry=entry, **updates)

    if body.custom_metrics is not None:
        await _validate_custom_metrics(
            db, person_id=entry.person_id, custom_metrics=body.custom_metrics
        )
        entry = await replace_custom_metric_values(db, entry=entry, values=body.custom_metrics)
    return _to_entry_out(entry)


@router.delete(
    "/life-tracking-entries/{entry_id}", status_code=204, dependencies=[Depends(require_csrf)]
)
async def delete_life_tracking_entry_route(
    entry_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    entry = await get_life_tracking_entry_for_user(db, entry_id=entry_id, user_id=user.id)
    if entry is None:
        raise NotFoundError(f"life tracking entry {entry_id} not found")
    await delete_life_tracking_entry(db, entry=entry)


@router.post(
    "/people/{person_id}/custom-metric-definitions",
    response_model=CustomMetricDefinitionOut,
    status_code=201,
    dependencies=[Depends(require_csrf)],
)
async def create_custom_metric_definition_route(
    person_id: uuid.UUID,
    body: CustomMetricDefinitionCreateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CustomMetricDefinitionOut:
    await _require_person(db, person_id=person_id, user_id=user.id)

    existing = await get_custom_metric_definition_by_key(
        db, person_id=person_id, metric_key=body.metric_key
    )
    if existing is not None:
        raise MetricKeyImmutable(
            f"metric_key {body.metric_key!r} already exists for person {person_id}"
        )

    definition = await create_custom_metric_definition(
        db,
        person_id=person_id,
        metric_key=body.metric_key,
        label=body.label,
        scale_min=body.scale_min,
        scale_max=body.scale_max,
        active=True,
    )
    return _to_definition_out(definition)


@router.get(
    "/people/{person_id}/custom-metric-definitions",
    response_model=list[CustomMetricDefinitionOut],
)
async def list_custom_metric_definitions_route(
    person_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[CustomMetricDefinitionOut]:
    await _require_person(db, person_id=person_id, user_id=user.id)
    definitions = await list_custom_metric_definitions_for_person(db, person_id=person_id)
    return [_to_definition_out(definition) for definition in definitions]


@router.patch(
    "/custom-metric-definitions/{definition_id}",
    response_model=CustomMetricDefinitionOut,
    dependencies=[Depends(require_csrf)],
)
async def patch_custom_metric_definition_route(
    definition_id: uuid.UUID,
    body: CustomMetricDefinitionPatchRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CustomMetricDefinitionOut:
    """Nur `label` und `active` sind aenderbar. `metric_key` steht gar nicht im
    Request-Schema -- Unveraenderlichkeit ist hier keine Laufzeitpruefung, sondern
    strukturell nicht ausdrueckbar."""
    definition = await get_custom_metric_definition_for_user(
        db, definition_id=definition_id, user_id=user.id
    )
    if definition is None:
        raise NotFoundError(f"custom metric definition {definition_id} not found")

    set_fields = body.model_fields_set
    updates: dict[str, object] = {}
    if "label" in set_fields and body.label is not None:
        updates["label"] = body.label
    if "active" in set_fields and body.active is not None:
        updates["active"] = body.active
        # Stilllegen setzt den Soft-Delete-Zeitstempel, Reaktivieren raeumt ihn ab --
        # gleiches Muster wie `CheckinDimension.retired_at`.
        updates["retired_at"] = None if body.active else dt.datetime.now(dt.UTC)

    if updates:
        definition = await update_custom_metric_definition(db, definition=definition, **updates)
    return _to_definition_out(definition)
