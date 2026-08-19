from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from numra_api.deps import (
    get_current_user,
    get_db,
    get_export_storage,
    get_pdf_client,
    require_csrf,
)
from numra_api.models import Export, User
from numra_api.repositories.exports import list_exports_for_user
from numra_api.schemas.export import ExportCreateRequest, ExportOut
from numra_api.services.export_service import create_export, get_export_file
from numra_api.services.pdf_client import PdfServiceClient
from numra_api.storage.exports import ExportStorage

router = APIRouter(prefix="/v1", tags=["exports"])


def _export_to_out(export: Export) -> ExportOut:
    return ExportOut(
        id=str(export.id),
        report_id=str(export.report_id) if export.report_id else None,
        export_type=export.export_type,
        status=export.status,
        file_size_bytes=export.file_size_bytes,
        error_code=export.error_code,
        created_at=export.created_at,
    )


@router.post(
    "/exports", response_model=ExportOut, status_code=201, dependencies=[Depends(require_csrf)]
)
async def create_export_route(
    body: ExportCreateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    storage: ExportStorage = Depends(get_export_storage),
    pdf_client: PdfServiceClient = Depends(get_pdf_client),
) -> ExportOut:
    export = await create_export(
        db,
        user_id=user.id,
        report_id=uuid.UUID(body.report_id),
        export_type=body.export_type,
        storage=storage,
        pdf_client=pdf_client,
    )
    return _export_to_out(export)


@router.get("/exports", response_model=list[ExportOut])
async def list_exports_route(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ExportOut]:
    exports = await list_exports_for_user(db, user_id=user.id)
    return [_export_to_out(export) for export in exports]


@router.get("/exports/{export_id}/download")
async def download_export_route(
    export_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    storage: ExportStorage = Depends(get_export_storage),
) -> Response:
    export, content = await get_export_file(
        db, user_id=user.id, export_id=export_id, storage=storage
    )
    media_type = "application/pdf" if export.export_type == "pdf" else "application/octet-stream"
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="numra-export-{export.id}.pdf"'},
    )
