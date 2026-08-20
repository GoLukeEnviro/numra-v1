from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from numra_api.models import Export
from numra_api.models.enums import ExportStatus, ExportType


async def create_export_record(
    db: AsyncSession, *, user_id: uuid.UUID, report_id: uuid.UUID, export_type: ExportType
) -> Export:
    export = Export(
        user_id=user_id, report_id=report_id, export_type=export_type, status=ExportStatus.PENDING
    )
    db.add(export)
    await db.flush()
    return export


async def mark_export_complete(
    db: AsyncSession, *, export: Export, file_ref: str, file_size_bytes: int
) -> None:
    export.status = ExportStatus.COMPLETE
    export.file_ref = file_ref
    export.file_size_bytes = file_size_bytes
    await db.flush()


async def mark_export_failed(db: AsyncSession, *, export: Export, error_code: str) -> None:
    export.status = ExportStatus.FAILED
    export.error_code = error_code[:80]
    await db.flush()


async def get_export_for_user(
    db: AsyncSession, *, export_id: uuid.UUID, user_id: uuid.UUID
) -> Export | None:
    stmt = select(Export).where(Export.id == export_id, Export.user_id == user_id)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def list_exports_for_user(db: AsyncSession, *, user_id: uuid.UUID) -> list[Export]:
    stmt = select(Export).where(Export.user_id == user_id).order_by(Export.created_at.desc())
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def list_file_refs_for_user(db: AsyncSession, *, user_id: uuid.UUID) -> list[str]:
    """Every non-null `file_ref` this user's exports currently point at — used by
    account delete-all to remove the physical files before the DB rows cascade away
    (see routes/account.py)."""
    stmt = select(Export.file_ref).where(Export.user_id == user_id, Export.file_ref.is_not(None))
    result = await db.execute(stmt)
    return [ref for ref in result.scalars().all() if ref is not None]
