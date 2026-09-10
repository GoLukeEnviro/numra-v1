"""PR-V2-06 -- persistence for `CheckinTemplate`/`CheckinDimension`/
`RelationshipCheckin`/`CheckinResponse`/`CheckinAnalysis`.

Privacy boundary (specs/v2/checkin-spec.md Section 19, specs/v2/privacy-spec.md
Section 49): raw `CheckinResponse.value` is `SUBMITTER_ONLY`. Every function here
that can return a `value` is either explicitly scoped to one `user_id`
(`get_responses_for_checkin_and_user`) or explicitly marked internal-only
(`get_dimension_values_for_checkin_internal`, consumed exclusively by
services/checkin_service.py to build the shared `CheckinAnalysis` -- its return
value must never be forwarded to a route response).
"""

from __future__ import annotations

import datetime as dt
import uuid
from collections import defaultdict
from collections.abc import Mapping

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from numra_api.models import (
    CheckinAnalysis,
    CheckinDimension,
    CheckinResponse,
    CheckinRoundDimension,
    CheckinTemplate,
    RelationshipCheckin,
)
from numra_api.models.enums import CheckinStatus


async def get_active_template(
    db: AsyncSession, *, workspace_id: uuid.UUID
) -> CheckinTemplate | None:
    stmt = select(CheckinTemplate).where(
        CheckinTemplate.workspace_id == workspace_id, CheckinTemplate.active.is_(True)
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def create_template(
    db: AsyncSession, *, workspace_id: uuid.UUID, version: int
) -> CheckinTemplate:
    template = CheckinTemplate(workspace_id=workspace_id, version=version)
    db.add(template)
    await db.flush()
    return template


async def create_dimension(
    db: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    template_version: int,
    semantic_key: str,
    label: str,
    description: str | None = None,
    scale_min: int = 1,
    scale_max: int = 10,
    sort_order: int = 0,
    dimension_class: str | None = None,
) -> CheckinDimension:
    dimension = CheckinDimension(
        workspace_id=workspace_id,
        template_version=template_version,
        semantic_key=semantic_key,
        label=label,
        description=description,
        scale_min=scale_min,
        scale_max=scale_max,
        sort_order=sort_order,
        dimension_class=dimension_class,
    )
    db.add(dimension)
    await db.flush()
    return dimension


async def list_dimensions(
    db: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    template_version: int,
    active_only: bool = False,
) -> list[CheckinDimension]:
    stmt = (
        select(CheckinDimension)
        .where(
            CheckinDimension.workspace_id == workspace_id,
            CheckinDimension.template_version == template_version,
        )
        .order_by(CheckinDimension.sort_order.asc())
    )
    if active_only:
        stmt = stmt.where(CheckinDimension.active.is_(True))
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_dimension_by_id(
    db: AsyncSession, *, workspace_id: uuid.UUID, dimension_id: uuid.UUID
) -> CheckinDimension | None:
    stmt = select(CheckinDimension).where(
        CheckinDimension.id == dimension_id, CheckinDimension.workspace_id == workspace_id
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def get_dimension_by_semantic_key(
    db: AsyncSession, *, workspace_id: uuid.UUID, semantic_key: str
) -> CheckinDimension | None:
    """Includes retired rows -- a `semantic_key` must never be reused, active or not
    (see `SemanticKeyImmutable`)."""
    stmt = select(CheckinDimension).where(
        CheckinDimension.workspace_id == workspace_id,
        CheckinDimension.semantic_key == semantic_key,
    )
    result = await db.execute(stmt)
    return result.scalars().first()


async def get_active_dimension_by_semantic_key(
    db: AsyncSession, *, workspace_id: uuid.UUID, semantic_key: str
) -> CheckinDimension | None:
    stmt = select(CheckinDimension).where(
        CheckinDimension.workspace_id == workspace_id,
        CheckinDimension.semantic_key == semantic_key,
        CheckinDimension.active.is_(True),
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def get_awaiting_checkin(
    db: AsyncSession, *, workspace_id: uuid.UUID
) -> RelationshipCheckin | None:
    stmt = select(RelationshipCheckin).where(
        RelationshipCheckin.workspace_id == workspace_id,
        RelationshipCheckin.status == CheckinStatus.AWAITING_SUBMISSIONS,
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def create_checkin(
    db: AsyncSession, *, workspace_id: uuid.UUID, checkin_template_version: int
) -> RelationshipCheckin:
    checkin = RelationshipCheckin(
        workspace_id=workspace_id, checkin_template_version=checkin_template_version
    )
    db.add(checkin)
    await db.flush()
    return checkin


async def get_checkin_by_id(
    db: AsyncSession, *, workspace_id: uuid.UUID, checkin_id: uuid.UUID
) -> RelationshipCheckin | None:
    stmt = select(RelationshipCheckin).where(
        RelationshipCheckin.id == checkin_id, RelationshipCheckin.workspace_id == workspace_id
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def list_checkins_for_workspace(
    db: AsyncSession, *, workspace_id: uuid.UUID, limit: int, offset: int
) -> list[RelationshipCheckin]:
    stmt = (
        select(RelationshipCheckin)
        .where(RelationshipCheckin.workspace_id == workspace_id)
        .order_by(RelationshipCheckin.cycle_started_at.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def count_user_responses(
    db: AsyncSession, *, checkin_id: uuid.UUID, user_id: uuid.UUID
) -> int:
    stmt = (
        select(func.count())
        .select_from(CheckinResponse)
        .where(CheckinResponse.checkin_id == checkin_id, CheckinResponse.user_id == user_id)
    )
    result = await db.execute(stmt)
    return int(result.scalar_one())


async def count_distinct_submitters(db: AsyncSession, *, checkin_id: uuid.UUID) -> int:
    stmt = select(func.count(func.distinct(CheckinResponse.user_id))).where(
        CheckinResponse.checkin_id == checkin_id
    )
    result = await db.execute(stmt)
    return int(result.scalar_one())


def build_response_rows(
    *,
    checkin_id: uuid.UUID,
    user_id: uuid.UUID,
    dimensions_by_id: dict[uuid.UUID, CheckinRoundDimension],
    responses: list[tuple[uuid.UUID, int]],
) -> list[CheckinResponse] | None:
    """Pure helper -- returns `None` if any `dimension_id` is not part of
    `dimensions_by_id` (workspace/active-template scoped by the caller), so the
    service layer can turn that into an IDOR-safe 404 instead of a raw KeyError."""
    rows: list[CheckinResponse] = []
    for dimension_id, value in responses:
        dimension = dimensions_by_id.get(dimension_id)
        if dimension is None:
            return None
        rows.append(
            CheckinResponse(
                checkin_id=checkin_id,
                user_id=user_id,
                dimension_id=dimension.dimension_id,
                semantic_key=dimension.semantic_key,
                value=value,
            )
        )
    return rows


async def get_responses_for_checkin_and_user(
    db: AsyncSession, *, checkin_id: uuid.UUID, user_id: uuid.UUID
) -> list[CheckinResponse]:
    """SUBMITTER-SCOPED read -- always filters on `user_id` in addition to
    `checkin_id`. This is the ONLY repository function a route may call to render raw
    `CheckinResponse.value`s back to a caller."""
    stmt = select(CheckinResponse).where(
        CheckinResponse.checkin_id == checkin_id, CheckinResponse.user_id == user_id
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_dimension_values_for_checkin_internal(
    db: AsyncSession, *, checkin_id: uuid.UUID
) -> dict[str, dict[uuid.UUID, int]]:
    """INTERNAL ONLY -- returns every submitted value for `checkin_id` across BOTH
    members, grouped by `semantic_key` then `user_id`. Consumed exclusively by
    services/checkin_service.py::submit_checkin to compute the shared
    `CheckinAnalysis` once both members have submitted. This function's return value
    must never be serialized into an HTTP response or otherwise leave the service
    layer -- routes/checkins.py must never call this directly."""
    stmt = select(CheckinResponse).where(CheckinResponse.checkin_id == checkin_id)
    result = await db.execute(stmt)
    grouped: dict[str, dict[uuid.UUID, int]] = defaultdict(dict)
    for response in result.scalars().all():
        grouped[response.semantic_key][response.user_id] = response.value
    return grouped


async def mark_checkin_analyzed(
    db: AsyncSession, *, checkin: RelationshipCheckin
) -> RelationshipCheckin:
    checkin.status = CheckinStatus.ANALYZED
    await db.flush()
    return checkin


async def create_analysis(
    db: AsyncSession,
    *,
    checkin_id: uuid.UUID,
    workspace_id: uuid.UUID,
    checkin_template_version: int,
    result_json: Mapping[str, object],
) -> CheckinAnalysis:
    analysis = CheckinAnalysis(
        checkin_id=checkin_id,
        workspace_id=workspace_id,
        checkin_template_version=checkin_template_version,
        result_json=result_json,
    )
    db.add(analysis)
    await db.flush()
    return analysis


async def get_analysis_for_checkin(
    db: AsyncSession, *, checkin_id: uuid.UUID
) -> CheckinAnalysis | None:
    stmt = select(CheckinAnalysis).where(CheckinAnalysis.checkin_id == checkin_id)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def list_prior_analyses(
    db: AsyncSession, *, workspace_id: uuid.UUID, checkin_template_version: int
) -> list[CheckinAnalysis]:
    """Ordered oldest-to-newest, scoped to `(workspace_id, checkin_template_version)`
    -- the trend-segmentation boundary from specs/v2/checkin-spec.md ("Trend
    calculations correctly segment by checkin_template_version")."""
    stmt = (
        select(CheckinAnalysis)
        .where(
            CheckinAnalysis.workspace_id == workspace_id,
            CheckinAnalysis.checkin_template_version == checkin_template_version,
        )
        .order_by(CheckinAnalysis.computed_at.asc())
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def retire_dimension(
    db: AsyncSession, *, dimension: CheckinDimension, retired_at: dt.datetime
) -> CheckinDimension:
    dimension.active = False
    dimension.retired_at = retired_at
    await db.flush()
    return dimension


__all__ = [
    "build_response_rows",
    "count_distinct_submitters",
    "count_user_responses",
    "create_analysis",
    "create_checkin",
    "create_dimension",
    "create_template",
    "get_active_dimension_by_semantic_key",
    "get_active_template",
    "get_analysis_for_checkin",
    "get_awaiting_checkin",
    "get_checkin_by_id",
    "get_dimension_by_id",
    "get_dimension_by_semantic_key",
    "get_dimension_values_for_checkin_internal",
    "get_responses_for_checkin_and_user",
    "list_checkins_for_workspace",
    "list_dimensions",
    "list_prior_analyses",
    "mark_checkin_analyzed",
    "retire_dimension",
]


async def list_round_dimensions(
    db: AsyncSession, *, checkin_id: uuid.UUID
) -> list[CheckinRoundDimension]:
    result = await db.execute(
        select(CheckinRoundDimension)
        .where(CheckinRoundDimension.checkin_id == checkin_id)
        .order_by(CheckinRoundDimension.sort_order, CheckinRoundDimension.dimension_id)
    )
    return list(result.scalars())
