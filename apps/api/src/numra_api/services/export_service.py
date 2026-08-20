"""Orchestrates one export: validate the source report is actually complete, render it
via the internal PDF service, persist the bytes through `ExportStorage`, and record the
result. No calculation or report-generation logic lives here — an export is always a
rendering of an already-complete `Report`, never a source of new facts.
"""

from __future__ import annotations

import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from numra_api.models import Export
from numra_api.models.enums import ExportStatus, ExportType
from numra_api.repositories.exports import (
    create_export_record,
    get_export_for_user,
    mark_export_complete,
    mark_export_failed,
)
from numra_api.repositories.reports import get_report_for_user
from numra_api.services.errors import NotFoundError, ReportNotReady
from numra_api.services.pdf_client import PdfServiceClient, PdfServiceUnavailable
from numra_api.storage.exports import ExportStorage

_EXTENSION_BY_TYPE: dict[ExportType, str] = {ExportType.PDF: "pdf"}

logger = logging.getLogger(__name__)


async def create_export(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    report_id: uuid.UUID,
    export_type: ExportType,
    storage: ExportStorage,
    pdf_client: PdfServiceClient,
) -> Export:
    report = await get_report_for_user(db, report_id=report_id, user_id=user_id)
    if report is None:
        raise NotFoundError(f"report {report_id} not found")
    if report.status != "COMPLETE" or report.content_json is None:
        raise ReportNotReady(f"report {report_id} is not COMPLETE yet (status={report.status})")
    if export_type is not ExportType.PDF:
        raise NotFoundError(f"unsupported export_type: {export_type!r}")

    export = await create_export_record(
        db, user_id=user_id, report_id=report.id, export_type=export_type
    )

    person_payload = report.profile_snapshot.get("person", {})
    try:
        pdf_bytes = await pdf_client.render_report_pdf(
            report=report.content_json, profile=report.profile_snapshot, person=person_payload
        )
    except PdfServiceUnavailable as exc:
        # PdfServiceUnavailable's own message is already safe to log in full -- it
        # never carries the internal bearer token or raw low-level exception
        # internals (see its docstring) -- and a failed render being completely
        # silent otherwise (nothing printed anywhere, only a DB column no one is
        # looking at) makes this exact failure mode undiagnosable in production too,
        # not just in CI.
        logger.warning(
            "PDF export failed for export_id=%s report_id=%s: %s", export.id, report.id, exc
        )
        await mark_export_failed(db, export=export, error_code=f"PDF_RENDER_FAILED: {exc}")
        return export

    file_ref = await storage.save(
        export_id=export.id, content=pdf_bytes, extension=_EXTENSION_BY_TYPE[export_type]
    )
    await mark_export_complete(db, export=export, file_ref=file_ref, file_size_bytes=len(pdf_bytes))
    return export


async def get_export_file(
    db: AsyncSession, *, user_id: uuid.UUID, export_id: uuid.UUID, storage: ExportStorage
) -> tuple[Export, bytes]:
    export = await get_export_for_user(db, export_id=export_id, user_id=user_id)
    if export is None:
        raise NotFoundError(f"export {export_id} not found")
    if export.status != ExportStatus.COMPLETE or export.file_ref is None:
        raise ReportNotReady(f"export {export_id} is not COMPLETE yet (status={export.status})")
    content = await storage.read(export.file_ref)
    return export, content
