"""PR-V2-06 -- orchestration for configurable check-ins
(specs/v2/checkin-spec.md). Synchronous submission flow, no job/worker: the shared
`CheckinAnalysis` is computed in the same transaction as the second member's
submission (see `submit_checkin`). NO LLM import anywhere in this module.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import numra_api.repositories.checkins as checkins_repo
from numra_api.models import (
    CheckinAnalysis,
    CheckinDimension,
    CheckinIdempotency,
    CheckinResponse,
    CheckinRoundDimension,
    CheckinTemplate,
    RelationshipCheckin,
    RelationshipWorkspace,
)
from numra_api.models.enums import CheckinStatus, WorkspaceStatus
from numra_api.repositories.workspaces import get_workspace_member, lock_workspace
from numra_api.services.checkin_analysis_service import compute_checkin_analysis
from numra_api.services.errors import (
    CheckinAlreadySubmitted,
    CheckinIdempotencyConflict,
    CheckinNoDimensions,
    CheckinResponsesIncomplete,
    CheckinRoundMismatch,
    CheckinRoundOpen,
    CheckinScaleInvalid,
    CheckinValueOutOfRange,
    DimensionNotAllowedForRelationshipType,
    NotFoundError,
    SemanticKeyImmutable,
)
from numra_api.services.workspace_guard import assert_workspace_active

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
    dimensions: list[CheckinRoundDimension]
    partner_submitted: bool


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


async def require_locked_workspace(
    db: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
    active: bool = True,
) -> RelationshipWorkspace:
    _require_member(
        await get_workspace_member(db, workspace_id=workspace_id, user_id=user_id),
        workspace_id=workspace_id,
    )
    workspace = await lock_workspace(db, workspace_id=workspace_id)
    _require_member(workspace, workspace_id=workspace_id)
    assert workspace is not None
    # Authorization is fresh even if acquisition waited for account deletion.
    _require_member(
        await get_workspace_member(db, workspace_id=workspace_id, user_id=user_id),
        workspace_id=workspace_id,
    )
    if active:
        await assert_workspace_active(db, workspace=workspace)
    return workspace


async def assert_no_open_round(db: AsyncSession, *, workspace_id: uuid.UUID) -> None:
    if await checkins_repo.get_awaiting_checkin(db, workspace_id=workspace_id) is not None:
        raise CheckinRoundOpen("configuration is locked while a check-in round is open")


async def get_checkin_template(
    db: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
    version: int | None = None,
) -> tuple[CheckinTemplate, list[CheckinDimension]]:
    workspace = await require_locked_workspace(
        db, workspace_id=workspace_id, user_id=user_id, active=False
    )
    if version is not None:
        template = (
            await db.execute(
                select(CheckinTemplate).where(
                    CheckinTemplate.workspace_id == workspace_id, CheckinTemplate.version == version
                )
            )
        ).scalar_one_or_none()
    else:
        template = await checkins_repo.get_active_template(db, workspace_id=workspace_id)
        if template is None and workspace.status != WorkspaceStatus.DISSOLVED:
            template = await get_or_create_active_template(db, workspace_id=workspace_id)
    if template is None:
        raise NotFoundError("check-in template not found")
    dimensions = await checkins_repo.list_dimensions(
        db, workspace_id=workspace_id, template_version=template.version
    )
    return template, dimensions


async def editable_template(db: AsyncSession, *, workspace_id: uuid.UUID) -> CheckinTemplate:
    """Caller holds workspace lock. First round freezes a version; no response-dependent race."""
    template = await get_or_create_active_template(db, workspace_id=workspace_id)
    used = (
        await db.execute(
            select(RelationshipCheckin.id)
            .where(
                RelationshipCheckin.workspace_id == workspace_id,
                RelationshipCheckin.checkin_template_version == template.version,
            )
            .limit(1)
        )
    ).scalar_one_or_none()
    if used is None:
        return template
    dimensions = await checkins_repo.list_dimensions(
        db, workspace_id=workspace_id, template_version=template.version
    )
    template.active = False
    await db.flush()
    new = await checkins_repo.create_template(
        db, workspace_id=workspace_id, version=template.version + 1
    )
    for d in dimensions:
        db.add(
            CheckinDimension(
                workspace_id=workspace_id,
                template_version=new.version,
                semantic_key=d.semantic_key,
                label=d.label,
                description=d.description,
                scale_min=d.scale_min,
                scale_max=d.scale_max,
                sort_order=d.sort_order,
                dimension_class=d.dimension_class,
                active=d.active,
                retired_at=d.retired_at,
            )
        )
    await db.flush()
    return new


def _is_restricted(*, dimension_class: str | None, relationship_type: str | None) -> bool:
    # Managed minors cannot be members of a two-account RelationshipWorkspace.
    # Free text cannot be semantically classified here; no keyword heuristics.
    return dimension_class == "INTIMATE" and relationship_type in _RESTRICTED_RELATIONSHIP_TYPES


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
    dimension_class: str | None = None,
) -> CheckinDimension:
    workspace = await require_locked_workspace(db, workspace_id=workspace_id, user_id=user_id)
    await assert_no_open_round(db, workspace_id=workspace_id)
    if not 0 <= scale_min < scale_max <= 100:
        raise CheckinScaleInvalid("scale must satisfy 0 <= min < max <= 100")
    if semantic_key in _RESTRICTED_DIMENSION_KEYS:
        dimension_class = "INTIMATE"
    if _is_restricted(
        dimension_class=dimension_class, relationship_type=workspace.relationship_type
    ):
        raise DimensionNotAllowedForRelationshipType("dimension class is not allowed for this type")
    await get_or_create_active_template(db, workspace_id=workspace_id)
    if (
        await checkins_repo.get_dimension_by_semantic_key(
            db, workspace_id=workspace_id, semantic_key=semantic_key
        )
        is not None
    ):
        raise SemanticKeyImmutable("semantic_key already exists; retire it and use a new key")
    template = await editable_template(db, workspace_id=workspace_id)
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
        dimension_class=dimension_class,
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
    workspace = await require_locked_workspace(db, workspace_id=workspace_id, user_id=user_id)
    await assert_no_open_round(db, workspace_id=workspace_id)
    original = await checkins_repo.get_dimension_by_id(
        db, workspace_id=workspace_id, dimension_id=dimension_id
    )
    if original is None:
        raise NotFoundError("dimension not found")
    template = await editable_template(db, workspace_id=workspace_id)
    # A stale ID addresses the same semantic identity in the current version.
    dimension = (
        await db.execute(
            select(CheckinDimension).where(
                CheckinDimension.workspace_id == workspace_id,
                CheckinDimension.template_version == template.version,
                CheckinDimension.semantic_key == original.semantic_key,
            )
        )
    ).scalar_one()
    if active is True and _is_restricted(
        dimension_class=dimension.dimension_class, relationship_type=workspace.relationship_type
    ):
        raise DimensionNotAllowedForRelationshipType("dimension class is not allowed for this type")
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
    db: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    relationship_type: str,
) -> None:
    """Called under workspace lock after the open-round guard; versioning also applies here."""
    if relationship_type not in _RESTRICTED_RELATIONSHIP_TYPES:
        return
    template = await checkins_repo.get_active_template(db, workspace_id=workspace_id)
    if template is None:
        return
    dimensions = await checkins_repo.list_dimensions(
        db, workspace_id=workspace_id, template_version=template.version
    )
    if not any(d.active and d.dimension_class == "INTIMATE" for d in dimensions):
        return
    template = await editable_template(db, workspace_id=workspace_id)
    for d in await checkins_repo.list_dimensions(
        db, workspace_id=workspace_id, template_version=template.version
    ):
        if d.active and d.dimension_class == "INTIMATE":
            await checkins_repo.retire_dimension(
                db, dimension=d, retired_at=dt.datetime.now(dt.UTC)
            )


def payload_hash(round_id: uuid.UUID | None, responses: list[tuple[uuid.UUID, int]]) -> str:
    canonical = json.dumps(
        {
            "round_id": str(round_id) if round_id else None,
            "responses": sorted((str(d), v) for d, v in responses),
        },
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


async def lookup_attempt(
    db: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
    operation: str,
    key: str,
    digest: str,
) -> CheckinIdempotency | None:
    attempt = await db.get(CheckinIdempotency, (workspace_id, user_id, operation, key))
    if attempt is not None and attempt.payload_hash != digest:
        raise CheckinIdempotencyConflict("Idempotency-Key was used with a different payload")
    return attempt


async def start_checkin_round(
    db: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
    idempotency_key: str,
) -> CheckinSubmissionResult:
    await require_locked_workspace(db, workspace_id=workspace_id, user_id=user_id)
    digest = payload_hash(None, [])
    attempt = await lookup_attempt(
        db,
        workspace_id=workspace_id,
        user_id=user_id,
        operation="START",
        key=idempotency_key,
        digest=digest,
    )
    if attempt is not None:
        return await get_checkin(
            db, workspace_id=workspace_id, user_id=user_id, checkin_id=attempt.checkin_id
        )
    await assert_no_open_round(db, workspace_id=workspace_id)
    template = await get_or_create_active_template(db, workspace_id=workspace_id)
    dimensions = await checkins_repo.list_dimensions(
        db, workspace_id=workspace_id, template_version=template.version, active_only=True
    )
    if not dimensions:
        raise CheckinNoDimensions("activate at least one dimension before starting a round")
    checkin = await checkins_repo.create_checkin(
        db, workspace_id=workspace_id, checkin_template_version=template.version
    )
    checkin.snapshot_origin = "ROUND_START"
    for d in dimensions:
        db.add(
            CheckinRoundDimension(
                checkin_id=checkin.id,
                dimension_id=d.id,
                semantic_key=d.semantic_key,
                label=d.label,
                description=d.description,
                scale_min=d.scale_min,
                scale_max=d.scale_max,
                sort_order=d.sort_order,
            )
        )
    db.add(
        CheckinIdempotency(
            workspace_id=workspace_id,
            user_id=user_id,
            operation="START",
            key=idempotency_key,
            payload_hash=digest,
            checkin_id=checkin.id,
        )
    )
    await db.flush()
    return await get_checkin(db, workspace_id=workspace_id, user_id=user_id, checkin_id=checkin.id)


async def submit_checkin(
    db: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
    round_id: uuid.UUID,
    idempotency_key: str,
    responses: list[tuple[uuid.UUID, int]],
) -> CheckinSubmissionResult:
    await require_locked_workspace(db, workspace_id=workspace_id, user_id=user_id)
    digest = payload_hash(round_id, responses)
    attempt = await lookup_attempt(
        db,
        workspace_id=workspace_id,
        user_id=user_id,
        operation="SUBMIT",
        key=idempotency_key,
        digest=digest,
    )
    if attempt is not None:
        return await get_checkin(
            db, workspace_id=workspace_id, user_id=user_id, checkin_id=attempt.checkin_id
        )
    checkin = await checkins_repo.get_checkin_by_id(
        db, workspace_id=workspace_id, checkin_id=round_id
    )
    if checkin is None:
        raise CheckinRoundMismatch("round is not available for submission")
    if await checkins_repo.count_user_responses(db, checkin_id=checkin.id, user_id=user_id):
        raise CheckinAlreadySubmitted(checkin.id)
    if checkin.status != CheckinStatus.AWAITING_SUBMISSIONS:
        raise CheckinRoundMismatch("round is not available for submission")
    dimensions = await checkins_repo.list_round_dimensions(db, checkin_id=checkin.id)
    dimensions_by_id = {d.dimension_id: d for d in dimensions}
    ids = [d for d, _ in responses]
    if not dimensions or len(ids) != len(set(ids)) or set(ids) != set(dimensions_by_id):
        raise CheckinResponsesIncomplete("provide exactly one answer for every snapshot dimension")
    for dimension_id, value in responses:
        d = dimensions_by_id[dimension_id]
        if not d.scale_min <= value <= d.scale_max:
            raise CheckinValueOutOfRange(
                f"dimension {d.dimension_id}: allowed {d.scale_min}..{d.scale_max}"
            )
    rows = checkins_repo.build_response_rows(
        checkin_id=checkin.id,
        user_id=user_id,
        dimensions_by_id=dimensions_by_id,
        responses=responses,
    )
    assert rows is not None
    db.add_all(rows)
    await db.flush()

    submitter_count = await checkins_repo.count_distinct_submitters(db, checkin_id=checkin.id)
    if submitter_count >= 2:
        values_by_key = await checkins_repo.get_dimension_values_for_checkin_internal(
            db, checkin_id=checkin.id
        )
        dimension_values: dict[str, tuple[int, int]] = {}
        for semantic_key, values_by_user in values_by_key.items():
            if len(values_by_user) != 2:
                raise CheckinResponsesIncomplete("inconsistent stored submission")
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
        await checkins_repo.create_analysis(
            db,
            checkin_id=checkin.id,
            workspace_id=workspace_id,
            checkin_template_version=checkin.checkin_template_version,
            result_json=result_json,
        )
        await checkins_repo.mark_checkin_analyzed(db, checkin=checkin)

    db.add(
        CheckinIdempotency(
            workspace_id=workspace_id,
            user_id=user_id,
            operation="SUBMIT",
            key=idempotency_key,
            payload_hash=digest,
            checkin_id=checkin.id,
        )
    )
    await db.flush()
    return await get_checkin(db, workspace_id=workspace_id, user_id=user_id, checkin_id=checkin.id)


async def get_checkin(
    db: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
    checkin_id: uuid.UUID,
) -> CheckinSubmissionResult:
    await require_locked_workspace(db, workspace_id=workspace_id, user_id=user_id, active=False)
    checkin = await checkins_repo.get_checkin_by_id(
        db, workspace_id=workspace_id, checkin_id=checkin_id
    )
    if checkin is None:
        raise NotFoundError("checkin not found")
    mine = await checkins_repo.get_responses_for_checkin_and_user(
        db, checkin_id=checkin.id, user_id=user_id
    )
    analysis = await checkins_repo.get_analysis_for_checkin(db, checkin_id=checkin.id)
    dimensions = await checkins_repo.list_round_dimensions(db, checkin_id=checkin.id)
    partner = (
        await db.execute(
            select(CheckinResponse.id)
            .where(CheckinResponse.checkin_id == checkin.id, CheckinResponse.user_id != user_id)
            .limit(1)
        )
    ).scalar_one_or_none() is not None
    return CheckinSubmissionResult(checkin, mine, analysis, dimensions, partner)


async def get_current_checkin(
    db: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
) -> CheckinSubmissionResult | None:
    await require_locked_workspace(db, workspace_id=workspace_id, user_id=user_id, active=False)
    checkin = await checkins_repo.get_awaiting_checkin(db, workspace_id=workspace_id)
    if checkin is None:
        latest = await checkins_repo.list_checkins_for_workspace(
            db, workspace_id=workspace_id, limit=1, offset=0
        )
        checkin = latest[0] if latest else None
    if checkin is None:
        return None
    return await get_checkin(db, workspace_id=workspace_id, user_id=user_id, checkin_id=checkin.id)


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
