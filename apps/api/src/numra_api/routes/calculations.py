from __future__ import annotations

import datetime as dt
import uuid
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from numra_api.deps import get_current_user, get_db, require_csrf
from numra_api.models import User
from numra_api.repositories.calculations import (
    get_calculation_for_user,
    list_calculations_for_person,
)
from numra_api.repositories.people import get_person
from numra_api.schemas.calculation import CalculateRequest, CalculationOut, CalculationSummaryOut
from numra_api.services.calculation_service import (
    person_input_from_row,
    run_and_persist_calculation,
)
from numra_api.services.errors import NotFoundError
from numra_numerology.engine import calculate_profile

router = APIRouter(prefix="/v1", tags=["calculations"])


def _to_out(calc) -> CalculationOut:  # type: ignore[no-untyped-def]
    return CalculationOut(
        id=str(calc.id),
        person_id=str(calc.person_id),
        calculation_version=calc.calculation_version,
        schema_version=calc.schema_version,
        as_of_date=calc.as_of_date,
        deterministic_hash=calc.deterministic_hash,
        canonical_profile=calc.canonical_profile_json,
        created_at=calc.created_at,
    )


def _to_summary(calc) -> CalculationSummaryOut:  # type: ignore[no-untyped-def]
    return CalculationSummaryOut(
        id=str(calc.id),
        person_id=str(calc.person_id),
        as_of_date=calc.as_of_date,
        calculation_version=calc.calculation_version,
        schema_version=calc.schema_version,
        deterministic_hash=calc.deterministic_hash,
        created_at=calc.created_at,
    )


@router.post(
    "/people/{person_id}/calculations",
    response_model=CalculationOut,
    status_code=201,
    dependencies=[Depends(require_csrf)],
)
async def create_calculation_route(
    person_id: uuid.UUID,
    body: CalculateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CalculationOut:
    person = await get_person(db, person_id=person_id, user_id=user.id)
    if person is None:
        raise NotFoundError(f"person {person_id} not found")
    calculation = await run_and_persist_calculation(db, person=person, as_of_date=body.as_of_date)
    return _to_out(calculation)


@router.get("/people/{person_id}/calculations", response_model=list[CalculationSummaryOut])
async def list_calculations_route(
    person_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[CalculationSummaryOut]:
    person = await get_person(db, person_id=person_id, user_id=user.id)
    if person is None:
        raise NotFoundError(f"person {person_id} not found")
    calculations = await list_calculations_for_person(
        db, person_id=person_id, user_id=user.id, limit=limit, offset=offset
    )
    return [_to_summary(calc) for calc in calculations]


@router.get("/calculations/{calculation_id}", response_model=CalculationOut)
async def get_calculation_route(
    calculation_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CalculationOut:
    calculation = await get_calculation_for_user(db, calculation_id=calculation_id, user_id=user.id)
    if calculation is None:
        raise NotFoundError(f"calculation {calculation_id} not found")
    return _to_out(calculation)


@router.get("/people/{person_id}/timing")
async def get_timing_route(
    person_id: uuid.UUID,
    as_of_date: dt.date,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Ad-hoc, non-persisted timing lookup — recomputes the engine for the given
    as_of_date without creating a new immutable Calculation snapshot."""
    person = await get_person(db, person_id=person_id, user_id=user.id)
    if person is None:
        raise NotFoundError(f"person {person_id} not found")
    person_input = person_input_from_row(person)
    profile = calculate_profile(person_input, as_of_date=as_of_date)
    timing: dict[str, Any] = profile.model_dump(mode="json")["timing"]
    return timing
