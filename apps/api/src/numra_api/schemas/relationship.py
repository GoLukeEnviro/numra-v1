from __future__ import annotations

import datetime as dt
from typing import Any

from pydantic import BaseModel


class RelationshipCreateRequest(BaseModel):
    calculation_a_id: str
    calculation_b_id: str


class RelationshipOut(BaseModel):
    id: str
    calculation_a_id: str
    calculation_b_id: str
    comparison: dict[str, Any]
    created_at: dt.datetime
