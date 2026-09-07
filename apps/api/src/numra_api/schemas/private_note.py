from __future__ import annotations

import datetime as dt
import uuid

from pydantic import BaseModel


class PrivateNoteCreateRequest(BaseModel):
    title: str | None = None
    content: str


class PrivateNotePatchRequest(BaseModel):
    """Every field optional; `exclude_unset`/`model_fields_set` at the route means
    only fields the client actually sent are applied -- same pattern as
    `PersonPatchRequest` (schemas/person.py)."""

    title: str | None = None
    content: str | None = None


class PrivateNoteOut(BaseModel):
    id: uuid.UUID
    person_id: uuid.UUID
    title: str | None
    content: str
    created_at: dt.datetime
    updated_at: dt.datetime

    model_config = {"from_attributes": True}
