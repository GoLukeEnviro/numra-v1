from __future__ import annotations

import datetime as dt
import uuid

from pydantic import BaseModel


class PrivateReflectionCreateRequest(BaseModel):
    entry_date: dt.date
    content: str


class PrivateReflectionPatchRequest(BaseModel):
    """Every field optional; `exclude_unset`/`model_fields_set` at the route means
    only fields the client actually sent are applied -- same pattern as
    `PersonPatchRequest` (schemas/person.py)."""

    entry_date: dt.date | None = None
    content: str | None = None


class PrivateReflectionOut(BaseModel):
    id: uuid.UUID
    person_id: uuid.UUID
    entry_date: dt.date
    content: str
    created_at: dt.datetime
    updated_at: dt.datetime

    model_config = {"from_attributes": True}


class PrivateReflectionSummaryOut(BaseModel):
    """Workspace-overview shape: just enough to identify and link to the latest
    entry -- no full `content` payload (see schemas/workspace.py)."""

    id: uuid.UUID
    entry_date: dt.date
    created_at: dt.datetime

    model_config = {"from_attributes": True}
