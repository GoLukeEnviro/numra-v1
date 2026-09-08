"""PR-V2-06 -- orchestration for configurable check-ins
(specs/v2/checkin-spec.md). Synchronous submission flow, no job/worker: the shared
`CheckinAnalysis` is computed in the same transaction as the second member's
submission (see `submit_checkin`). NO LLM import anywhere in this module.
"""

from __future__ import annotations

import datetime as dt
import uuid
from dataclasses import dataclass

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

import numra_api.repositories.checkins as checkins_repo
from numra_api.models import (
    CheckinAnalysis,
    CheckinDimension,
    CheckinResponse,
    CheckinTemplate,
    RelationshipCheckin,
)
from numra_api.repositories.workspaces import get_workspace_by_id, get_workspace_member
from numra_api.services.checkin_analysis_service import compute_checkin_analysis
from numra_api.services.errors import (
    CheckinAlreadySubmitted,
    DimensionNotAllowedForRelationshipType,
    NotFoundError,
    SemanticKeyImmutable,
)
from numra_api.services.workspace_guard import assert_workspace_active_by_id

#: specs/v2/checkin-spec.md -- dimensions of this "class" are gated per
#: `_RESTRICTED_RELATIONSHIP_TYPES`, enforced at BOTH creation time
#: (`create_custom_dimension`) and on a later relationship_type change
#: (`auto_retire_restricted_dimensions`, hooked from
#: services/relationship_workspace_service.py::patch_relationship_type).
_RESTRICTED_DIMENSION_KEYS = frozenset({"sexual_connection"})
_RESTRICTED_RELATIONSHIP_TYPES = frozenset({"PARENT_CHILD", "SIBLINGS", "WORK"})

#: specs/v2/checkin-spec.md -- the default template (version 1) ships with exactly
#: these five dimensions, scale 1..10, sort_order 0..4. `sexual_connection` is
#: deliberately NOT part of the default set -- it is only ever added as a custom
#: dimension (subject to the gating above).
_DEFAULT_DIMENSIONS: tuple[tuple[str, str], ...] = (
    ("closeness", "Closeness"),
    ("communication", "Communication"),
    ("understanding", "Understanding"),
    ("autonomy", "Autonomy"),
    ("conflict_load", "Conflict Load"),
)


@dataclass
class CheckinSubmissionResult:
    checkin: RelationshipCheckin
    my_responses: list[CheckinResponse]
    analysis: CheckinAnalysis | None


def _require_member(member: object, *, workspace_id: uuid.UUID) -> None:
    if member is None:
        # IDOR-anti-enumeration -- never 403, see every other workspace-scoped
        # endpoint in this repo (routes/consent.py, routes/relationship_workspaces.py).
        raise NotFoundError(f"workspace {workspace_id} not found")


async def get_or_create_active_template(
    db: AsyncSession, *, workspace_id: uuid.UUID
) -> CheckinTemplate:
    template = await checkins_repo.get_active_template(db, workspace_id=workspace_id)
    if template is not None:
        return template

    template = await checkins_repo.create_template(db, workspace_id=workspace_id, version=1)
    for sort_order, (semantic_key, label) in enumerate(_DEFAULT_DIMENSIONS):
        await checkins_repo.create_dimension(
            db,
            workspace_id=workspace_id,
            template_version=template.version,
            semantic_key=semantic_key,
            label=label,
            sort_order=sort_order,
        )
    return template


async def get_checkin_template(
    db: AsyncSession, *, workspace_id: uuid.UUID, user_id: uuid.UUID
) -> tuple[CheckinTemplate, list[CheckinDimension]]:
    member = await get_workspace_member(db, workspace_id=workspace_id, user_id=user_id)
    _require_member(member, workspace_id=workspace_id)

    template = await get_or_create_active_template(db, workspace_id=workspace_id)
    dimensions = await checkins_repo.list_dimensions(
        db, workspace_id=workspace_id, template_version=template.version
    )
    return template, dimensions


def _is_restricted(*, semantic_key: str, relationship_type: str | None) -> bool:
    """`relationship_type is None` is NOT treated as restrictive (spec: gating only
    fires for the three named types, an unset type is not one of them)."""
    return (
        semantic_key in _RESTRICTED_DIMENSION_KEYS
        and relationship_type in _RESTRICTED_RELATIONSHIP_TYPES
    )


async def create_custom_dimension(
    db: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
    semantic_key: str,
    label: str,
    description: str | None,
    scale_min: int,
    scale_max: int,
    sort_order: int,
) -> CheckinDimension:
    member = await get_workspace_member(db, workspace_id=workspace_id, user_id=user_id)
    _require_member(member, workspace_id=workspace_id)

    workspace = await get_workspace_by_id(db, workspace_id=workspace_id)
    _require_member(workspace, workspace_id=workspace_id)
    assert workspace is not None  # narrowed by _require_member above

    if _is_restricted(semantic_key=semantic_key, relationship_type=workspace.relationship_type):
        raise DimensionNotAllowedForRelationshipType(
            f"dimension '{semantic_key}' is not allowed for relationship_type "
            f"'{workspace.relationship_type}'"
        )

    existing = await checkins_repo.get_dimension_by_semantic_key(
        db, workspace_id=workspace_id, semantic_key=semantic_key
    )
    if existing is not None:
        raise SemanticKeyImmutable(f"semantic_key '{semantic_key}' already exists")

    template = await get_or_create_active_template(db, workspace_id=workspace_id)
    return await checkins_repo.create_dimension(
        db,
        workspace_id=workspace_id,
        template_version=template.version,
        semantic_key=semantic_key,
        label=label,
        description=description,
        scale_min=scale_min,
        scale_max=scale_max,
        sort_order=sort_order,
    )


async def update_dimension(
    db: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
    dimension_id: uuid.UUID,
    label: str | None,
    description: str | None,
    active: bool | None,
) -> CheckinDimension:
    member = await get_workspace_member(db, workspace_id=workspace_id, user_id=user_id)
    _require_member(member, workspace_id=workspace_id)

    dimension = await checkins_repo.get_dimension_by_id(
        db, workspace_id=workspace_id, dimension_id=dimension_id
    )
    if dimension is None:
        raise NotFoundError(f"dimension {dimension_id} not found")

    if active is True and dimension.active is False:
        workspace = await get_workspace_by_id(db, workspace_id=workspace_id)
        if workspace is not None and _is_restricted(
            semantic_key=dimension.semantic_key, relationship_type=workspace.relationship_type
        ):
            raise DimensionNotAllowedForRelationshipType(
                f"dimension '{dimension.semantic_key}' is not allowed for relationship_type "
                f"'{workspace.relationship_type}'"
            )

    if label is not None:
        dimension.label = label
    if description is not None:
        dimension.description = description
    if active is not None:
        dimension.active = active
        dimension.retired_at = None if active else dt.datetime.now(dt.UTC)

    await db.flush()
    return dimension


async def auto_retire_restricted_dimensions(
    db: AsyncSession, *, workspace_id: uuid.UUID, relationship_type: str
) -> None:
    """Hooked from services/relationship_workspace_service.py::patch_relationship_type
    right after a `relationship_type` update. No-op unless the new type is one of
    `_RESTRICTED_RELATIONSHIP_TYPES`."""
    if relationship_type not in _RESTRICTED_RELATIONSHIP_TYPES:
        return
    for semantic_key in _RESTRICTED_DIMENSION_KEYS:
        dimension = await checkins_repo.get_active_dimension_by_semantic_key(
            db, workspace_id=workspace_id, semantic_key=semantic_key
        )
        if dimension is not None:
            await checkins_repo.retire_dimension(
                db, dimension=dimension, retired_at=dt.datetime.now(dt.UTC)
            )


async def submit_checkin(
    db: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
    responses: list[tuple[uuid.UUID, int]],
) -> CheckinSubmissionResult:
    member = await get_workspace_member(db, workspace_id=workspace_id, user_id=user_id)
    _require_member(member, workspace_id=workspace_id)

    await assert_workspace_active_by_id(db, workspace_id=workspace_id)

    template = await get_or_create_active_template(db, workspace_id=workspace_id)

    checkin = await checkins_repo.get_awaiting_checkin(db, workspace_id=workspace_id)
    if checkin is None:
        try:
            checkin = await checkins_repo.create_checkin(
                db, workspace_id=workspace_id, checkin_template_version=template.version
            )
            await db.flush()
        except IntegrityError:
            # uq_relationship_checkins_one_awaiting_per_workspace -- the other member's
            # first-submission request created the round in a concurrent transaction
            # between our read above and this insert (both saw None under READ
            # COMMITTED). Roll back our losing insert and submit onto the winner's
            # round instead of silently starting a second, orphaned cycle that would
            # never reach two submitters.
            await db.rollback()
            checkin = await checkins_repo.get_awaiting_checkin(db, workspace_id=workspace_id)
            if checkin is None:  # pragma: no cover -- should be unreachable
                raise

    already_submitted = await checkins_repo.count_user_responses(
        db, checkin_id=checkin.id, user_id=user_id
    )
    if already_submitted > 0:
        raise CheckinAlreadySubmitted(checkin.id)

    active_dimensions = await checkins_repo.list_dimensions(
        db,
        workspace_id=workspace_id,
        template_version=checkin.checkin_template_version,
        active_only=True,
    )
    dimensions_by_id = {d.id: d for d in active_dimensions}
    rows = checkins_repo.build_response_rows(
        checkin_id=checkin.id,
        user_id=user_id,
        dimensions_by_id=dimensions_by_id,
        responses=responses,
    )
    if rows is None:
        # An unknown/foreign/inactive dimension_id -- IDOR-safe 404, never a 422 that
        # would confirm/deny the id's existence in another workspace.
        raise NotFoundError("one or more submitted dimensions were not found")

    db.add_all(rows)
    try:
        await db.flush()
    except IntegrityError as exc:
        # uq_checkin_responses_checkin_user_dimension -- a concurrent duplicate
        # submission for the same round. Same translate-IntegrityError pattern as
        # routes/people.py::AmbiguousSelfProfile.
        await db.rollback()
        raise CheckinAlreadySubmitted(checkin.id) from exc

    submitter_count = await checkins_repo.count_distinct_submitters(db, checkin_id=checkin.id)
    analysis: CheckinAnalysis | None = None
    if submitter_count >= 2:
        values_by_key = await checkins_repo.get_dimension_values_for_checkin_internal(
            db, checkin_id=checkin.id
        )
        dimension_values: dict[str, tuple[int, int]] = {}
        for semantic_key, values_by_user in values_by_key.items():
            if len(values_by_user) < 2:
                continue
            user_a_id, user_b_id = sorted(values_by_user, key=str)
            dimension_values[semantic_key] = (
                values_by_user[user_a_id],
                values_by_user[user_b_id],
            )

        prior_analyses = await checkins_repo.list_prior_analyses(
            db,
            workspace_id=workspace_id,
            checkin_template_version=checkin.checkin_template_version,
        )
        historical_gaps_by_key: dict[str, list[int]] = {key: [] for key in dimension_values}
        for prior in prior_analyses:
            for semantic_key, entry in prior.result_json.items():
                if semantic_key in historical_gaps_by_key:
                    historical_gaps_by_key[semantic_key].append(entry["absolute_gap"])

        result_json = compute_checkin_analysis(
            dimension_values=dimension_values, historical_gaps_by_key=historical_gaps_by_key
        )
        analysis = await checkins_repo.create_analysis(
            db,
            checkin_id=checkin.id,
            workspace_id=workspace_id,
            checkin_template_version=checkin.checkin_template_version,
            result_json=result_json,
        )
        await checkins_repo.mark_checkin_analyzed(db, checkin=checkin)

    my_responses = await checkins_repo.get_responses_for_checkin_and_user(
        db, checkin_id=checkin.id, user_id=user_id
    )
    return CheckinSubmissionResult(checkin=checkin, my_responses=my_responses, analysis=analysis)


async def get_checkin(
    db: AsyncSession, *, workspace_id: uuid.UUID, user_id: uuid.UUID, checkin_id: uuid.UUID
) -> tuple[RelationshipCheckin, list[CheckinResponse], CheckinAnalysis | None]:
    member = await get_workspace_member(db, workspace_id=workspace_id, user_id=user_id)
    _require_member(member, workspace_id=workspace_id)

    checkin = await checkins_repo.get_checkin_by_id(
        db, workspace_id=workspace_id, checkin_id=checkin_id
    )
    if checkin is None:
        raise NotFoundError(f"checkin {checkin_id} not found")

    my_responses = await checkins_repo.get_responses_for_checkin_and_user(
        db, checkin_id=checkin.id, user_id=user_id
    )
    analysis = await checkins_repo.get_analysis_for_checkin(db, checkin_id=checkin.id)
    return checkin, my_responses, analysis


async def list_checkins(
    db: AsyncSession, *, workspace_id: uuid.UUID, user_id: uuid.UUID, limit: int, offset: int
) -> list[RelationshipCheckin]:
    member = await get_workspace_member(db, workspace_id=workspace_id, user_id=user_id)
    _require_member(member, workspace_id=workspace_id)

    return await checkins_repo.list_checkins_for_workspace(
        db, workspace_id=workspace_id, limit=limit, offset=offset
    )


__all__ = [
    "CheckinSubmissionResult",
    "auto_retire_restricted_dimensions",
    "create_custom_dimension",
    "get_checkin",
    "get_checkin_template",
    "get_or_create_active_template",
    "list_checkins",
    "submit_checkin",
    "update_dimension",
]
