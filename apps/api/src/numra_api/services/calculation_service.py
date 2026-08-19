from __future__ import annotations

import datetime as dt

from sqlalchemy.ext.asyncio import AsyncSession

from numra_api.models import Calculation, Person
from numra_api.repositories.calculations import create_calculation
from numra_numerology.engine import calculate_profile
from numra_numerology.models.person import BirthPlace, BirthTime, PersonInput


def person_input_from_row(person: Person) -> PersonInput:
    return PersonInput(
        birth_first_names=person.birth_first_names,
        birth_middle_names=person.birth_middle_names,
        birth_last_name=person.birth_last_name,
        birth_date=person.birth_date,
        birth_time=BirthTime.model_validate(person.birth_time) if person.birth_time else None,
        birth_place=BirthPlace.model_validate(person.birth_place) if person.birth_place else None,
        current_first_names=person.current_first_names,
        current_middle_names=person.current_middle_names,
        current_last_name=person.current_last_name,
        preferred_name=person.preferred_name,
    )


async def run_and_persist_calculation(
    db: AsyncSession, *, person: Person, as_of_date: dt.date
) -> Calculation:
    person_input = person_input_from_row(person)
    profile = calculate_profile(person_input, as_of_date=as_of_date)

    return await create_calculation(
        db,
        person_id=person.id,
        calculation_version=profile.calculation_version,
        schema_version=profile.schema_version,
        as_of_date=as_of_date,
        input_snapshot=person_input.model_dump(mode="json"),
        canonical_profile_json=profile.model_dump(mode="json"),
        deterministic_hash=profile.deterministic_hash or "",
    )
