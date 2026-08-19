from __future__ import annotations

import datetime as dt
import uuid

from pydantic import BaseModel

from numra_numerology.models.person import BirthPlace, BirthTime


class PersonPatchRequest(BaseModel):
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
