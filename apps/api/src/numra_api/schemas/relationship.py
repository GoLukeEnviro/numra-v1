from __future__ import annotations

import datetime as dt
from typing import Any

from pydantic import BaseModel

from numra_api.schemas.person_ref import PersonRefOut


class RelationshipCreateRequest(BaseModel):
    calculation_a_id: str
    calculation_b_id: str


class RelationshipOut(BaseModel):
    id: str
    calculation_a_id: str
    calculation_b_id: str
    person_a: PersonRefOut
    person_b: PersonRefOut
    comparison: dict[str, Any]
    created_at: dt.datetime


class RelationshipSummaryOut(BaseModel):
    """Relationship-library list shape: resolved person names instead of raw
    calculation UUIDs, so a list card never needs a LocalStorage cache to say who
    Person A/B are. No `comparison` payload — that's a detail-view concern."""

    id: str
    person_a: PersonRefOut
    person_b: PersonRefOut
    created_at: dt.datetime
