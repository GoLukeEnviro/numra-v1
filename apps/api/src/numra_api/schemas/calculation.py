from __future__ import annotations

import datetime as dt
from typing import Any

from pydantic import BaseModel


class CalculateRequest(BaseModel):
    as_of_date: dt.date


class CalculationOut(BaseModel):
    id: str
    person_id: str
    calculation_version: str
    schema_version: str
    as_of_date: dt.date
    deterministic_hash: str
    canonical_profile: dict[str, Any]
    created_at: dt.datetime


class CalculationSummaryOut(BaseModel):
    """History-list shape: no `canonical_profile` payload — list cards only need
    enough to identify and link to a snapshot, not the full profile JSON."""

    id: str
    person_id: str
    as_of_date: dt.date
    calculation_version: str
    schema_version: str
    deterministic_hash: str
    created_at: dt.datetime
