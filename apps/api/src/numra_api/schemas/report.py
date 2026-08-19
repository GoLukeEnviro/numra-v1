from __future__ import annotations

import datetime as dt
from typing import Any

from pydantic import BaseModel

from numra_api.models.enums import ReportJobStatus, ReportType


class ReportCreateRequest(BaseModel):
    calculation_id: str
    report_type: ReportType


class ReportOut(BaseModel):
    id: str
    calculation_id: str
    report_type: ReportType
    status: str
    calculation_version: str
    knowledge_version: str
    prompt_version: str
    content: dict[str, Any] | None
    generated_at: dt.datetime | None
    created_at: dt.datetime
    job_id: str


class ReportJobOut(BaseModel):
    id: str
    report_id: str
    status: ReportJobStatus
    progress: int
    attempt_count: int
    error_code: str | None
    created_at: dt.datetime
    updated_at: dt.datetime
