"""Orchestrates the Connection lifecycle: invite create/list/revoke/decline, and
accept -- which atomically claims the invitation, creates the `UserConnection`, its
`RelationshipWorkspace`, both `WorkspaceMember` rows, and the six default
`ConsentGrant` rows (3 scopes x 2 directions), all within the one request/session
transaction `deps.get_db` commits at the end (see CLAUDE.md service-stil pattern,
export_service.py for a comparable multi-table flow). No manual `db.begin()`.
"""

from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from numra_api.auth.tokens import generate_token, hash_token
from numra_api.config import Settings
from numra_api.models import ConnectionInvitation, RelationshipWorkspace, User, UserConnection
from numra_api.models.enums import (
    DEFAULT_CONSENT_SCOPES,
    ConnectionStatus,
    ConsentEventType,
    InvitationMethod,
    InvitationState,
)
from numra_api.repositories.connection_invitations import (
    claim_invitation_by_token_hash,
    create_connection_invitation,
    decline_invitation,
    get_invitation_by_token_hash,
    get_invitation_for_inviter,
    list_invitations_for_inviter,
    revoke_invitation,
)
from numra_api.repositories.connections import (
    conditionally_dissolve_connection,
    create_user_connection,
    get_active_connection_between,
    get_connection_for_user,
    list_connections_for_user,
)
from numra_api.repositories.consent import create_consent_event, create_consent_grant
from numra_api.repositories.workspaces import (
    conditionally_dissolve_workspace,
    create_relationship_workspace,
    create_workspace_member,
    get_workspace_for_connection,
)
from numra_api.services.consent_service import revoke_all_workspace_consent
from numra_api.services.errors import (
    CannotInviteSelf,
    ConnectionAlreadyExists,
    InvitationExpiredOrInvalid,
    InvitationNotFound,
    NotFoundError,
)

_INVITATION_TTL_DAYS = 14


async def create_invitation(
    db: AsyncSession,
    *,
    inviter: User,
    method: InvitationMethod,
    invitee_email: str | None,
    settings: Settings,
) -> tuple[ConnectionInvitation, str]:
    """Returns the invitation row plus the one-time plaintext token (only ever
    available here, at generation time -- never re-derivable from the persisted
    hash). `settings` is accepted for symmetry with the other token-issuing flows
    (auth_recovery_service.py) even though this PR's link is built by the route, not
    here."""
    # Self-invite is rejected distinctly (never a signal about a *different* account)
    # -- anti-enumeration for a genuinely foreign email is enforced by the route
    # always returning the same 201 shape regardless of match.
    if (
        method is InvitationMethod.EMAIL
        and invitee_email is not None
        and invitee_email.strip().lower() == inviter.email.strip().lower()
    ):
        raise CannotInviteSelf("cannot invite your own email address")

    token = generate_token()
    now = dt.datetime.now(dt.UTC)
    invitation = await create_connection_invitation(
        db,
        inviter_user_id=inviter.id,
        method=method,
        token_hash=hash_token(token),
        invitee_email=invitee_email,
        expires_at=now + dt.timedelta(days=_INVITATION_TTL_DAYS),
    )
    return invitation, token


async def list_invitations(
    db: AsyncSession, *, user_id: uuid.UUID, limit: int, offset: int
) -> list[ConnectionInvitation]:
    return await list_invitations_for_inviter(
        db, inviter_user_id=user_id, limit=limit, offset=offset
    )


async def preview_invitation(db: AsyncSession, *, token: str) -> ConnectionInvitation:
    invitation = await get_invitation_by_token_hash(db, token_hash=hash_token(token))
    if invitation is None:
        raise InvitationNotFound("invitation not found")
    now = dt.datetime.now(dt.UTC)
    if invitation.state != InvitationState.PENDING or invitation.expires_at <= now:
        raise InvitationExpiredOrInvalid("invitation is expired, used, or invalid")
    return invitation


async def revoke_own_invitation(
    db: AsyncSession, *, invitation_id: uuid.UUID, inviter_user_id: uuid.UUID
) -> ConnectionInvitation:
    invitation = await get_invitation_for_inviter(
        db, invitation_id=invitation_id, inviter_user_id=inviter_user_id
    )
    if invitation is None:
        raise InvitationNotFound(f"invitation {invitation_id} not found")
    if invitation.state != InvitationState.PENDING:
        raise InvitationExpiredOrInvalid("only a PENDING invitation can be revoked")
    return await revoke_invitation(db, invitation=invitation, now=dt.datetime.now(dt.UTC))


async def decline_own_invitation(
    db: AsyncSession, *, invitation_id: uuid.UUID, declining_user: User
) -> ConnectionInvitation:
    """Only the addressed invitee may decline. LINK/CODE invites have no invitee
    identity to check against until redeemed, so they are never declinable by id --
    the inviter revokes them instead. EMAIL invites are declinable only by the user
    whose own email matches `invitee_email` (case-insensitive, mirroring lookup)."""
    invitation = await db.get(ConnectionInvitation, invitation_id)
    if invitation is None:
        raise InvitationNotFound(f"invitation {invitation_id} not found")
    if (
        invitation.method != InvitationMethod.EMAIL
        or invitation.invitee_email is None
        or invitation.invitee_email.lower() != declining_user.email.lower()
    ):
        raise InvitationNotFound(f"invitation {invitation_id} not found")
    if invitation.state != InvitationState.PENDING:
        raise InvitationExpiredOrInvalid("only a PENDING invitation can be declined")
    return await decline_invitation(db, invitation=invitation)


async def accept_invitation(
    db: AsyncSession, *, token: str, redeeming_user: User
) -> tuple[UserConnection, RelationshipWorkspace]:
    """The one atomic multi-table flow: claim invitation -> UserConnection ->
    RelationshipWorkspace -> 2x WorkspaceMember -> 6x default ConsentGrant, all in this
    request's single `AsyncSession` (see module docstring)."""
    now = dt.datetime.now(dt.UTC)
    invitation = await claim_invitation_by_token_hash(
        db, token_hash=hash_token(token), redeemed_by_user_id=redeeming_user.id, now=now
    )
    if invitation is None:
        raise InvitationExpiredOrInvalid("invitation is expired, used, or invalid")

    if invitation.inviter_user_id == redeeming_user.id:
        raise CannotInviteSelf("cannot accept your own invitation")

    existing = await get_active_connection_between(
        db, user_id=invitation.inviter_user_id, other_user_id=redeeming_user.id
    )
    if existing is not None:
        raise ConnectionAlreadyExists("an active connection between these users already exists")

    connection = await create_user_connection(
        db, user_a_id=invitation.inviter_user_id, user_b_id=redeeming_user.id
    )
    workspace = await create_relationship_workspace(db, connection_id=connection.id)
    await create_workspace_member(db, workspace_id=workspace.id, user_id=invitation.inviter_user_id)
    await create_workspace_member(db, workspace_id=workspace.id, user_id=redeeming_user.id)

    for scope in DEFAULT_CONSENT_SCOPES:
        for grantor_id, grantee_id in (
            (invitation.inviter_user_id, redeeming_user.id),
            (redeeming_user.id, invitation.inviter_user_id),
        ):
            grant = await create_consent_grant(
                db,
                workspace_id=workspace.id,
                grantor_user_id=grantor_id,
                grantee_user_id=grantee_id,
                scope=scope,
            )
            await create_consent_event(
                db, grant_id=grant.id, event_type=ConsentEventType.GRANTED, actor_user_id=grantor_id
            )

    return connection, workspace


async def list_connections(
    db: AsyncSession, *, user_id: uuid.UUID, limit: int, offset: int
) -> list[UserConnection]:
    return await list_connections_for_user(db, user_id=user_id, limit=limit, offset=offset)


async def dissolve_own_connection(
    db: AsyncSession, *, connection_id: uuid.UUID, user_id: uuid.UUID
) -> UserConnection:
    """PR-V2-10 -- gehärteter Dissolve-Pfad: atomarer TOCTOU-safe Status-Übergang
    (statt read-then-setattr-then-flush) plus kaskadierender Consent-Revoke. Bereits
    `DISSOLVED` ist ein No-Op (idempotent) -- ein zweiter Dissolve-Aufruf darf weder
    crashen noch die Consent-Revoke-Side-Effects doppelt feuern."""
    connection = await get_connection_for_user(db, connection_id=connection_id, user_id=user_id)
    if connection is None:
        raise NotFoundError(f"connection {connection_id} not found")

    if connection.status == ConnectionStatus.DISSOLVED:
        return connection

    now = dt.datetime.now(dt.UTC)
    won = await conditionally_dissolve_connection(db, connection_id=connection.id, now=now)
    await db.refresh(connection)
    if not won:
        # Ein konkurrierender Dissolve-Aufruf hat gewonnen, während wir den Status
        # oben noch als ACTIVE gelesen haben -- derselbe Idempotenz-Vertrag wie oben,
        # kein Fehler, keine doppelten Side-Effects.
        return connection

    workspace = await get_workspace_for_connection(db, connection_id=connection.id)
    if workspace is not None:
        await conditionally_dissolve_workspace(db, workspace_id=workspace.id, now=now)
        await revoke_all_workspace_consent(
            db, workspace_id=workspace.id, actor_user_id=user_id, now=now
        )

    return connection
