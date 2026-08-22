from __future__ import annotations

import datetime as dt
import uuid

from pydantic import BaseModel

from numra_api.models.enums import NameIdentityKind
from numra_numerology.models.person import BirthPlace, BirthTime


class PersonPatchRequest(BaseModel):
    """Every field is optional and `exclude_unset` at the route means only fields the
    client actually sent are applied — the birth fields (V1.5 Epic B) intentionally
    reuse the same names as `PersonInput`/`PersonOut` rather than a separate
    "canon-sensitive" sub-object, since the route applies exactly one rule to all of
    them: editing a Person never touches any existing `Calculation` row (those are
    immutable snapshots, see `repositories/calculations.py`'s own docstring) — only a
    *new* calculation reflects the edit.
    """

    birth_first_names: str | None = None
    birth_middle_names: str | None = None
    birth_last_name: str | None = None
    birth_date: dt.date | None = None
    birth_time: BirthTime | None = None
    birth_place: BirthPlace | None = None
    current_first_names: str | None = None
    current_middle_names: str | None = None
    current_last_name: str | None = None
    preferred_name: str | None = None


class PersonOut(BaseModel):
    id: uuid.UUID
    birth_first_names: str
    birth_middle_names: str | None
    birth_last_name: str
    birth_date: dt.date
    birth_time: BirthTime | None
    birth_place: BirthPlace | None
    current_first_names: str | None
    current_middle_names: str | None
    current_last_name: str | None
    preferred_name: str | None
    created_at: dt.datetime
    updated_at: dt.datetime

    model_config = {"from_attributes": True}


class NameIdentityOut(BaseModel):
    """V1.5 Epic C: one recorded name Numra has held for a person. `recorded_at` is
    when Numra actually wrote this row down -- always present. `valid_from` is only
    ever set when the effective date is a genuinely known fact (the birth identity's
    `valid_from` is the birth date itself); it is `None` for current/preferred names,
    since no historical effective date is knowable for those -- never a guess."""

    id: uuid.UUID
    kind: NameIdentityKind
    first_names: str
    middle_names: str | None
    last_name: str
    valid_from: dt.date | None
    recorded_at: dt.datetime
