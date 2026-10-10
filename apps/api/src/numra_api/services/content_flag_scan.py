"""D6: read-only scan counting the stored results the strict detector flags (CLI
``content-flags scan``). Writes nothing and prints no text; identifiers only on request, so
an operator can tell the owners which results are affected. Regeneration is never started
from here -- it is an explicit user action (``POST .../regenerate``).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from numra_api.models import RelationshipAnalysis, Report, ReportSection
from numra_api.models.enums import ContentFlag
from numra_api.services.content_flag import analysis_flag, payload_flag, report_flags

__all__ = ["KindScan", "scan_stored_content"]

_BATCH = 50


@dataclass
class KindScan:
    checked: int = 0
    flagged_ids: list[uuid.UUID] = field(default_factory=list)

    @property
    def flagged(self) -> int:
        return len(self.flagged_ids)


async def scan_stored_content(db: AsyncSession) -> dict[str, KindScan]:
    """Counters per kind: reports, report sections (table rows) and relationship analyses.
    Only COMPLETE results with content are checked, in the mode of their pipeline."""
    scans = {
        "report": KindScan(),
        "report_section": KindScan(),
        "relationship_analysis": KindScan(),
    }

    reports = await db.stream_scalars(
        select(Report)
        .where(Report.status == "COMPLETE", Report.content_json.is_not(None))
        .order_by(Report.created_at)
        .execution_options(yield_per=_BATCH)
    )
    async for report in reports:
        scans["report"].checked += 1
        if report_flags(report).content_flag is not ContentFlag.NONE:
            scans["report"].flagged_ids.append(report.id)

    sections = await db.stream_scalars(
        select(ReportSection)
        .join(Report, Report.id == ReportSection.report_id)
        .where(Report.status == "COMPLETE")
        .order_by(ReportSection.created_at)
        .execution_options(yield_per=_BATCH)
    )
    async for section in sections:
        scans["report_section"].checked += 1
        if payload_flag(section.content_json, strict_braces=False) is not ContentFlag.NONE:
            scans["report_section"].flagged_ids.append(section.id)

    analyses = await db.stream_scalars(
        select(RelationshipAnalysis)
        .where(
            RelationshipAnalysis.status == "COMPLETE", RelationshipAnalysis.result_json.is_not(None)
        )
        .order_by(RelationshipAnalysis.created_at)
        .execution_options(yield_per=_BATCH)
    )
    async for analysis in analyses:
        scans["relationship_analysis"].checked += 1
        if analysis_flag(analysis) is not ContentFlag.NONE:
            scans["relationship_analysis"].flagged_ids.append(analysis.id)

    return scans
