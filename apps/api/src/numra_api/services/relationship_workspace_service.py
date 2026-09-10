"""OVERVIEW (metadata grid) + DUAL PROFILE (pure canon-number side-by-side) for
GET /v1/workspaces/{workspace_id}, and the relationship_type PATCH. Deliberately no
LLM-interpreted sections (COMMUNICATION/CLOSENESS/AUTONOMY/NEEDS/STRENGTHS/
CONFLICT DYNAMICS) -- see specs/v2/relationship-workspace-spec.md, PR-V2-05.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from numra_api.models import RelationshipWorkspace, User
from numra_api.models.enums import ConsentScope
from numra_api.repositories.calculations import get_latest_calculation_for_person
from numra_api.repositories.users import get_user_by_id
from numra_api.repositories.workspaces import (
    get_self_person_for_member,
    get_workspace_by_id,
    get_workspace_member,
    list_workspace_members,
    list_workspaces_for_user,
    update_relationship_type,
)
from numra_api.schemas.person_ref import PersonRefOut, person_display_name
from numra_api.schemas.relationship_workspace import DualProfileMemberOut
from numra_api.services.checkin_service import (
    assert_no_open_round,
    auto_retire_restricted_dimensions,
    require_locked_workspace,
)
from numra_api.services.consent_service import assert_consent
from numra_api.services.errors import ConsentNotGranted, NotFoundError

#: specs/v2/relationship-workspace-spec.md DUAL PROFILE -- pure canon numbers, no
#: interpretation. Mirrors services/relationship_service.py's metric set.
_CORE_NUMBER_METRICS: tuple[str, ...] = (
    "life_path",
    "expression",
    "soul_urge",
    "personality",
    "maturity",
)
_TIMING_METRICS: tuple[str, ...] = ("personal_year", "personal_month", "personal_day")


def _extract_metric(profile: dict[str, Any], section: str, metric_id: str) -> dict[str, Any] | None:
    section_data = profile.get(section)
    if not isinstance(section_data, dict):
        return None
    value = section_data.get(metric_id)
    return value if isinstance(value, dict) else None


def _build_core_numbers(profile: dict[str, Any]) -> dict[str, Any]:
    numbers: dict[str, Any] = {}
    for metric_id in _CORE_NUMBER_METRICS:
        metric = _extract_metric(profile, "core_numbers", metric_id)
        numbers[metric_id] = {
            "display_value": metric["display_value"] if metric else None,
            "effective_value": metric["effective_value"] if metric else None,
        }
    timing = profile.get("timing", {})
    for metric_id in _TIMING_METRICS:
        metric = timing.get(metric_id) if isinstance(timing, dict) else None
        numbers[metric_id] = {
            "display_value": metric["display_value"] if isinstance(metric, dict) else None,
            "effective_value": metric["effective_value"] if isinstance(metric, dict) else None,
        }
    return numbers


def _fallback_display_name(user: User | None, *, member_user_id: uuid.UUID) -> str:
    """Anzeigename, wenn kein sichtbares `SELF`-Person-Profil existiert (kein Profil
    angelegt, oder CORE_NUMEROLOGY nicht/nicht mehr freigegeben). `display_name_override`
    hat IMMER Vorrang vor `email`: bei einem gelöschten Account trägt es
    "Ehemaliges Mitglied" (services/account_deletion_service.py), und dessen -- beim
    Löschen ohnehin überschriebene -- E-Mail darf hier nie durchschlagen."""
    if user is None:
        return str(member_user_id)
    return user.display_name_override or user.email


async def _build_dual_profile_member(
    db: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    member_user_id: uuid.UUID,
    viewer_user_id: uuid.UUID,
) -> DualProfileMemberOut:
    """Own side (`member_user_id == viewer_user_id`) needs no consent check -- a user
    always sees their own numbers. The counterpart's side is gated by an active
    CORE_NUMEROLOGY grant from `member_user_id` to `viewer_user_id`, checked fresh
    right before serializing (defense-in-depth; CORE_NUMEROLOGY is auto-granted by
    default at workspace creation, see models/enums.py::DEFAULT_CONSENT_SCOPES) --
    a missing/revoked grant degrades that side to `core_numbers: null`, never a 403
    for the whole response."""
    member_user = await get_user_by_id(db, user_id=member_user_id)
    self_person = await get_self_person_for_member(db, user_id=member_user_id)

    display_name = _fallback_display_name(member_user, member_user_id=member_user_id)
    person_ref: PersonRefOut | None = None
    core_numbers: dict[str, Any] | None = None

    if self_person is not None:
        if member_user_id == viewer_user_id:
            can_view = True
        else:
            try:
                await assert_consent(
                    db,
                    workspace_id=workspace_id,
                    grantor_user_id=member_user_id,
                    grantee_user_id=viewer_user_id,
                    scope=ConsentScope.CORE_NUMEROLOGY,
                )
                can_view = True
            except ConsentNotGranted:
                can_view = False

        if can_view:
            display_name = person_display_name(
                preferred_name=self_person.preferred_name,
                birth_first_names=self_person.birth_first_names,
                birth_last_name=self_person.birth_last_name,
            )
            person_ref = PersonRefOut(id=self_person.id, display_name=display_name)

            calculation = await get_latest_calculation_for_person(
                db, person_id=self_person.id, user_id=member_user_id
            )
            if calculation is not None:
                core_numbers = _build_core_numbers(calculation.canonical_profile_json)

    return DualProfileMemberOut(
        user_id=member_user_id,
        display_name=display_name,
        self_person=person_ref,
        core_numbers=core_numbers,
    )


async def get_workspace_overview(
    db: AsyncSession, *, workspace_id: uuid.UUID, viewer_user_id: uuid.UUID
) -> tuple[RelationshipWorkspace, list[DualProfileMemberOut]]:
    member = await get_workspace_member(db, workspace_id=workspace_id, user_id=viewer_user_id)
    if member is None:
        raise NotFoundError(f"workspace {workspace_id} not found")

    workspace = await get_workspace_by_id(db, workspace_id=workspace_id)
    if workspace is None:
        raise NotFoundError(f"workspace {workspace_id} not found")

    members = await list_workspace_members(db, workspace_id=workspace_id)
    dual_profile = [
        await _build_dual_profile_member(
            db,
            workspace_id=workspace_id,
            member_user_id=m.user_id,
            viewer_user_id=viewer_user_id,
        )
        for m in members
    ]
    return workspace, dual_profile


async def patch_relationship_type(
    db: AsyncSession, *, workspace_id: uuid.UUID, user_id: uuid.UUID, relationship_type: str
) -> RelationshipWorkspace:
    member = await get_workspace_member(db, workspace_id=workspace_id, user_id=user_id)
    if member is None:
        raise NotFoundError(f"workspace {workspace_id} not found")

    workspace = await require_locked_workspace(db, workspace_id=workspace_id, user_id=user_id)
    if workspace.relationship_type == relationship_type:
        return workspace
    await assert_no_open_round(db, workspace_id=workspace_id)

    updated = await update_relationship_type(
        db, workspace=workspace, relationship_type=relationship_type
    )
    # PR-V2-06 minimal hook: a relationship_type change into a restricted type
    # (PARENT_CHILD/SIBLINGS/WORK) auto-retires any active sexual_connection-class
    # check-in dimension -- specs/v2/checkin-spec.md gating, enforced here as well as
    # at dimension-creation time (see services/checkin_service.py).
    await auto_retire_restricted_dimensions(
        db, workspace_id=workspace_id, relationship_type=relationship_type
    )
    return updated


async def list_workspaces_for_viewer(
    db: AsyncSession, *, user_id: uuid.UUID
) -> list[RelationshipWorkspace]:
    return await list_workspaces_for_user(db, user_id=user_id)


__all__ = [
    "get_workspace_overview",
    "list_workspaces_for_viewer",
    "patch_relationship_type",
]
