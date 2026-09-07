from __future__ import annotations

import datetime as dt
import uuid

from pydantic import BaseModel

from numra_api.models.enums import PersonalTaskStatus


class PersonalTaskCreateRequest(BaseModel):
    title: str
    description: str | None = None
    due_date: dt.date | None = None


class PersonalTaskPatchRequest(BaseModel):
    """Every field optional; `exclude_unset`/`model_fields_set` at the route means
    only fields the client actually sent are applied -- same pattern as
    `PersonPatchRequest` (schemas/person.py). `completed_at` is never accepted here
    -- it is derived server-side from a `status` transition into COMPLETED, see
    routes/personal_tasks.py."""

    title: str | None = None
    description: str | None = None
    due_date: dt.date | None = None
    status: PersonalTaskStatus | None = None


class PersonalTaskOut(BaseModel):
    id: uuid.UUID
    person_id: uuid.UUID
    title: str
    description: str | None
    due_date: dt.date | None
    status: PersonalTaskStatus
    completed_at: dt.datetime | None
    created_at: dt.datetime
    updated_at: dt.datetime

    model_config = {"from_attributes": True}
