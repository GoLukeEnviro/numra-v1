from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from numra_api.models import EvidencePolicy, PatternAnalysis


async def get_active_evidence_policy(db: AsyncSession) -> EvidencePolicy | None:
    """Genau eine aktive Version ist DB-erzwungen (partieller Unique-Index
    ``uq_evidence_policies_one_active``), deshalb reicht ``scalar_one_or_none`` --
    ein zweiter aktiver Datensatz waere ein Datenfehler und soll hier lautstark
    scheitern, nicht still die erste Zeile nehmen."""
    stmt = select(EvidencePolicy).where(EvidencePolicy.active.is_(True))
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def create_pattern_analysis(
    db: AsyncSession, *, person_id: uuid.UUID, user_id: uuid.UUID, **fields: Any
) -> PatternAnalysis:
    analysis = PatternAnalysis(person_id=person_id, user_id=user_id, **fields)
    db.add(analysis)
    await db.flush()
    return analysis


async def get_pattern_analysis_for_user(
    db: AsyncSession, *, analysis_id: uuid.UUID, user_id: uuid.UUID
) -> PatternAnalysis | None:
    stmt = select(PatternAnalysis).where(
        PatternAnalysis.id == analysis_id, PatternAnalysis.user_id == user_id
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def list_pattern_analyses_for_person(
    db: AsyncSession, *, person_id: uuid.UUID, user_id: uuid.UUID, limit: int, offset: int
) -> list[PatternAnalysis]:
    stmt = (
        select(PatternAnalysis)
        .where(PatternAnalysis.person_id == person_id, PatternAnalysis.user_id == user_id)
        .order_by(PatternAnalysis.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def delete_pattern_analysis(db: AsyncSession, *, analysis: PatternAnalysis) -> None:
    await db.delete(analysis)
