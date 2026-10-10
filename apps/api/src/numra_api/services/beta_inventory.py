"""D4 transition: read-only usage inventory and the explicit backfill of beta grants.

`collect_usage` only reads (counters per account, no content); accounts appear solely as
HMAC pseudonyms. `backfill_beta_access` is the ONLY writer and is never reached by a
migration or on startup -- the CLI (`numra_api.cli beta backfill`) is dry-run unless
``--apply`` is given. See docs/ops/2026-10-09-d4-beta-transition.md.
"""

from __future__ import annotations

import datetime as dt
import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute

from numra_api.models import (
    AnalysisJob,
    ChatMessage,
    EntitlementAssignment,
    PatternAnalysis,
    Report,
    User,
)
from numra_api.models.enums import AuditAction, ChatMessageRole
from numra_api.rate_limit import pseudonymous_key
from numra_api.repositories.audit import record_audit_event
from numra_api.repositories.entitlements import BETA_ACCESS_SET_KEY, grant_beta_access

__all__ = ["BackfillResult", "UsageRow", "backfill_beta_access", "collect_usage"]


@dataclass(frozen=True)
class UsageRow:
    user_id: uuid.UUID
    pseudonym: str
    is_active: bool
    reports: int
    analyses: int
    patterns: int
    copilot_messages: int
    granted: bool

    @property
    def total(self) -> int:
        return self.reports + self.analyses + self.patterns + self.copilot_messages


@dataclass(frozen=True)
class BackfillResult:
    candidates: int
    granted: int
    already_granted: int


async def _count_by_user(
    db: AsyncSession,
    user_column: InstrumentedAttribute[Any],
    created_column: InstrumentedAttribute[Any],
    since: dt.datetime | None,
) -> dict[uuid.UUID, int]:
    stmt = select(user_column, func.count()).group_by(user_column)
    if since is not None:
        stmt = stmt.where(created_column >= since)
    rows = (await db.execute(stmt)).all()
    return {user_id: count for user_id, count in rows if user_id is not None}


async def collect_usage(
    db: AsyncSession, *, secret: str, since: dt.datetime | None = None
) -> list[UsageRow]:
    """One row per account that used at least one cost-intensive feature (in the
    ``since`` window if given), most active first. Read-only."""
    reports = await _count_by_user(db, Report.user_id, Report.created_at, since)
    analyses = await _count_by_user(
        db, AnalysisJob.requested_by_user_id, AnalysisJob.created_at, since
    )
    patterns = await _count_by_user(db, PatternAnalysis.user_id, PatternAnalysis.created_at, since)

    copilot_stmt = (
        select(ChatMessage.author_user_id, func.count())
        .where(ChatMessage.role == ChatMessageRole.USER)
        .group_by(ChatMessage.author_user_id)
    )
    if since is not None:
        copilot_stmt = copilot_stmt.where(ChatMessage.created_at >= since)
    copilot = {
        user_id: count
        for user_id, count in (await db.execute(copilot_stmt)).all()
        if user_id is not None
    }

    used = set(reports) | set(analyses) | set(patterns) | set(copilot)
    if not used:
        return []
    granted = set((await db.execute(select(EntitlementAssignment.user_id))).scalars().all())
    active = {
        user_id: is_active
        for user_id, is_active in (
            await db.execute(select(User.id, User.is_active).where(User.id.in_(used)))
        ).all()
    }
    rows = [
        UsageRow(
            user_id=user_id,
            pseudonym=pseudonymous_key(str(user_id), secret=secret)[:12],
            is_active=active.get(user_id, False),
            reports=reports.get(user_id, 0),
            analyses=analyses.get(user_id, 0),
            patterns=patterns.get(user_id, 0),
            copilot_messages=copilot.get(user_id, 0),
            granted=user_id in granted,
        )
        for user_id in used
        if user_id in active
    ]
    return sorted(rows, key=lambda r: (-r.total, r.pseudonym))


async def backfill_beta_access(
    db: AsyncSession, *, rows: list[UsageRow], apply: bool, run_label: str
) -> BackfillResult:
    """Grants beta access to every active, not-yet-granted account in ``rows``. With
    ``apply=False`` nothing is written. Each grant is audited (actor NULL = CLI,
    ``source=cli_backfill``); a repeat run changes nothing. Caller commits."""
    candidates = [r for r in rows if r.is_active and not r.granted]
    already = sum(1 for r in rows if r.granted)
    granted = 0
    if apply:
        for row in candidates:
            if await grant_beta_access(db, user_id=row.user_id):
                granted += 1
                await record_audit_event(
                    db,
                    actor_user_id=None,
                    action=AuditAction.BETA_ACCESS_GRANTED,
                    target_user_id=row.user_id,
                    safe_metadata={
                        "entitlement_set": BETA_ACCESS_SET_KEY,
                        "source": "cli_backfill",
                        "run": run_label,
                    },
                )
    return BackfillResult(candidates=len(candidates), granted=granted, already_granted=already)
