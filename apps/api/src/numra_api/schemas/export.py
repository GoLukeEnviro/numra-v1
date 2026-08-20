from __future__ import annotations

import datetime as dt

from pydantic import BaseModel

from numra_api.models.enums import ExportStatus, ExportType


class ExportCreateRequest(BaseModel):
    report_id: str
    export_type: ExportType = ExportType.PDF


class ExportOut(BaseModel):
    id: str
    report_id: str | None
    export_type: ExportType
    status: ExportStatus
    file_size_bytes: int | None
    error_code: str | None
    created_at: dt.datetime
