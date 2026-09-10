"""Consent grant/revoke + the central `assert_consent` enforcement function later PRs
call before exposing any cross-user data inside a `RelationshipWorkspace`. No caching
layer anywhere here -- every check re-reads the DB (repositories/consent.py::
get_active_grant), so a revoke takes effect on the very next request.
"""

from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from numra_api.models import ConsentGrant
from numra_api.models.enums import ConsentEventType, WorkspaceMemberStatus
from numra_api.repositories.consent import (
    create_consent_event,
    create_consent_grant,
    get_active_grant,
    get_grant_for_key,
    get_grant_for_workspace,
    list_grants_for_workspace,
    reactivate_grant,
    revoke_all_active_grants_for_workspace,
    revoke_grant,
)
from numra_api.repositories.workspaces import get_workspace_member, list_workspace_members
from numra_api.services.errors import ConsentNotGranted, NotFoundError


async def grant_consent(
    db: AsyncSession, *, workspace_id: uuid.UUID, grantor_user_id: uuid.UUID, scope: str
) -> ConsentGrant:
    """Grants `scope` from `grantor_user_id` to the *other* ACTIVE member of the
    workspace. Requires the grantor to actually be an ACTIVE member (IDOR gate) --
    the grantee is derived from workspace membership, never accepted from the
    client."""
    grantor_member = await get_workspace_member(
        db, workspace_id=workspace_id, user_id=grantor_user_id
    )
    if grantor_member is None:
        raise NotFoundError(f"workspace {workspace_id} not found")

    grantee_user_id = await _other_member_user_id(
        db, workspace_id=workspace_id, user_id=grantor_user_id
    )

    # Idempotent -- granting an already-active scope (e.g. one of the 3 defaults
    # auto-granted at workspace creation) returns the existing row rather than
    # violating uq_consent_grants_workspace_grantor_grantee_scope_version.
    existing = await get_active_grant(
        db,
        workspace_id=workspace_id,
        grantor_user_id=grantor_user_id,
        grantee_user_id=grantee_user_id,
        scope=scope,
    )
    if existing is not None:
        return existing

    # Re-grant after revoke -- a revoked row already owns the unique slot for this
    # key (specs/v2/consent-spec.md: "Revocable ... at any time" implies re-grant).
    # Reactivate it and append a GRANTED event so the audit trail stays
    # GRANTED -> REVOKED -> GRANTED on one grant_id. `version` is untouched: it is
    # the scope-taxonomy version at creation time, not a re-grant counter.
    revoked = await get_grant_for_key(
        db,
        workspace_id=workspace_id,
        grantor_user_id=grantor_user_id,
        grantee_user_id=grantee_user_id,
        scope=scope,
    )
    if revoked is not None:
        grant = await reactivate_grant(db, grant=revoked)
        await create_consent_event(
            db,
            grant_id=grant.id,
            event_type=ConsentEventType.GRANTED,
            actor_user_id=grantor_user_id,
        )
        return grant

    grant = await create_consent_grant(
        db,
        workspace_id=workspace_id,
        grantor_user_id=grantor_user_id,
        grantee_user_id=grantee_user_id,
        scope=scope,
    )
    await create_consent_event(
        db, grant_id=grant.id, event_type=ConsentEventType.GRANTED, actor_user_id=grantor_user_id
    )
    return grant


async def revoke_consent(
    db: AsyncSession, *, workspace_id: uuid.UUID, grantor_user_id: uuid.UUID, scope: str
) -> ConsentGrant:
    """Only the original grantor may revoke -- `get_active_grant` filters on
    `grantor_user_id` so a caller can never revoke a grant they did not themselves
    make."""
    grantor_member = await get_workspace_member(
        db, workspace_id=workspace_id, user_id=grantor_user_id
    )
    if grantor_member is None:
        raise NotFoundError(f"workspace {workspace_id} not found")

    grantee_user_id = await _other_member_user_id(
        db, workspace_id=workspace_id, user_id=grantor_user_id
    )
    grant = await get_active_grant(
        db,
        workspace_id=workspace_id,
        grantor_user_id=grantor_user_id,
        grantee_user_id=grantee_user_id,
        scope=scope,
    )
    if grant is None:
        raise ConsentNotGranted(f"no active consent grant for scope {scope!r}")

    now = dt.datetime.now(dt.UTC)
    grant = await revoke_grant(db, grant=grant, now=now)
    await create_consent_event(
        db, grant_id=grant.id, event_type=ConsentEventType.REVOKED, actor_user_id=grantor_user_id
    )
    return grant


async def revoke_all_workspace_consent(
    db: AsyncSession, *, workspace_id: uuid.UUID, actor_user_id: uuid.UUID, now: dt.datetime
) -> list[ConsentGrant]:
    """PR-V2-10 -- kaskadierender Revoke aller noch aktiven Grants eines Workspace,
    beide Richtungen, in EINEM atomaren `UPDATE ... RETURNING`, plus je ein
    `ConsentEvent(REVOKED)` pro tatsächlich revoktem Grant. Bewusst ohne
    IDOR-/Grantor-Gate: die beiden Aufrufer (Dissolve und Account-Löschung) haben
    ihre Berechtigung bereits geprüft und revoken systemseitig beide Richtungen --
    anders als `revoke_consent`, wo nur der Grantor seinen eigenen Grant zurücknimmt.
    Idempotent: ein zweiter Aufruf findet nichts Aktives mehr und schreibt keine
    doppelten Events."""
    revoked = await revoke_all_active_grants_for_workspace(db, workspace_id=workspace_id, now=now)
    for grant in revoked:
        await create_consent_event(
            db, grant_id=grant.id, event_type=ConsentEventType.REVOKED, actor_user_id=actor_user_id
        )
    return revoked


async def assert_consent(
    db: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    grantor_user_id: uuid.UUID,
    grantee_user_id: uuid.UUID,
    scope: str,
) -> None:
    """Central enforcement function for later PRs -- raises `ConsentNotGranted` unless
    an active grant exists right now. Always reads fresh from the DB (see
    repositories/consent.py::get_active_grant docstring) -- never cached, so a revoke
    is effective immediately for the very next call."""
    grant = await get_active_grant(
        db,
        workspace_id=workspace_id,
        grantor_user_id=grantor_user_id,
        grantee_user_id=grantee_user_id,
        scope=scope,
    )
    if grant is None:
        raise ConsentNotGranted(f"consent for scope {scope!r} is not granted")


async def list_consent_for_workspace_member(
    db: AsyncSession, *, workspace_id: uuid.UUID, user_id: uuid.UUID
) -> list[ConsentGrant]:
    """Every grant in the workspace where `user_id` is grantor OR grantee -- the route
    (routes/consent.py) splits these into the two directions in the response."""
    member = await get_workspace_member(db, workspace_id=workspace_id, user_id=user_id)
    if member is None:
        raise NotFoundError(f"workspace {workspace_id} not found")
    grants = await list_grants_for_workspace(db, workspace_id=workspace_id)
    return [g for g in grants if g.grantor_user_id == user_id or g.grantee_user_id == user_id]


async def _other_member_user_id(
    db: AsyncSession, *, workspace_id: uuid.UUID, user_id: uuid.UUID
) -> uuid.UUID:
    """A `RelationshipWorkspace` always has exactly two ACTIVE members while both
    are still present (see services/connection_service.py) -- resolves the
    counterpart from membership rather than trusting a client-supplied grantee id.
    ACTIVE-gefiltert wie services/copilot_context_builder.py::
    _resolve_partner_user_id -- ein REMOVED-Mitglied (z.B. nach Account-Löschung
    des Partners) darf nie als Grantor/Grantee aufgelöst werden."""
    members = await list_workspace_members(db, workspace_id=workspace_id)
    active_user_ids = [m.user_id for m in members if m.status == WorkspaceMemberStatus.ACTIVE]
    other_user_ids = [uid for uid in active_user_ids if uid != user_id]
    if not other_user_ids:
        raise NotFoundError(f"workspace {workspace_id} has no counterpart member")
    return other_user_ids[0]


# Re-exported for callers that only need the read/lookup, not the mutating flows.
__all__ = [
    "assert_consent",
    "get_grant_for_workspace",
    "grant_consent",
    "list_consent_for_workspace_member",
    "revoke_all_workspace_consent",
    "revoke_consent",
]
