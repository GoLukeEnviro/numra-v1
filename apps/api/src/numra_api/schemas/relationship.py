from __future__ import annotations

import datetime as dt
from typing import Any

from pydantic import BaseModel, model_validator

from numra_api.schemas.person_ref import PersonRefOut


class RelationshipCreateRequest(BaseModel):
    """V1.5 Epic E: the primary, product-facing way to start a comparison is by
    person (`person_a_id`/`person_b_id`) — the route resolves each person's latest
    calculation server-side. `calculation_a_id`/`calculation_b_id` remain accepted
    directly for callers that already know a specific snapshot (e.g. comparing an
    older snapshot rather than the latest one) — exactly one of the two pairs must
    be supplied, never a mix."""

    person_a_id: str | None = None
    person_b_id: str | None = None
    calculation_a_id: str | None = None
    calculation_b_id: str | None = None

    @model_validator(mode="after")
    def _exactly_one_pair(self) -> RelationshipCreateRequest:
        by_person = self.person_a_id is not None and self.person_b_id is not None
        by_calculation = self.calculation_a_id is not None and self.calculation_b_id is not None
        if by_person == by_calculation:
            raise ValueError(
                "provide exactly one of (person_a_id, person_b_id) or "
                "(calculation_a_id, calculation_b_id)"
            )
        return self


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
