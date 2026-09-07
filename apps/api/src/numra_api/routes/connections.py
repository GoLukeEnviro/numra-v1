from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from numra_api.config import Settings
from numra_api.deps import (
    get_current_user,
    get_db,
    get_settings_dep,
    rate_limit_by_user,
    require_csrf,
)
from numra_api.models import ConnectionInvitation, User, UserConnection
from numra_api.schemas.connection import (
    ConnectionInvitationCreatedOut,
    ConnectionInvitationCreateRequest,
    ConnectionInvitationOut,
    ConnectionInvitationPreviewOut,
    RedeemInvitationRequest,
    RedeemInvitationResponseOut,
    UserConnectionOut,
)
from numra_api.services.connection_service import (
    accept_invitation,
    create_invitation,
    decline_own_invitation,
    dissolve_own_connection,
    list_connections,
    list_invitations,
    preview_invitation,
    revoke_own_invitation,
)

router = APIRouter(prefix="/v1/connections", tags=["connections"])


def _invitation_to_out(invitation: ConnectionInvitation) -> ConnectionInvitationOut:
    return ConnectionInvitationOut.model_validate(invitation, from_attributes=True)


def _connection_to_out(connection: UserConnection) -> UserConnectionOut:
    return UserConnectionOut.model_validate(connection, from_attributes=True)


@router.post(
    "/invitations",
    response_model=ConnectionInvitationCreatedOut,
    status_code=201,
    dependencies=[Depends(require_csrf)],
)
async def create_invitation_route(
    body: ConnectionInvitationCreateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings_dep),
    _rate_limit: None = Depends(
        rate_limit_by_user("connections:create_invitation", limit=10, window_seconds=3600)
    ),
) -> ConnectionInvitationCreatedOut:
    invitation, token = await create_invitation(
        db,
        inviter=user,
        method=body.method,
        invitee_email=body.invitee_email,
        settings=settings,
    )
    redeem_url = f"{settings.web_app_base_url}/connections/redeem?token={token}"
    return ConnectionInvitationCreatedOut(
        **_invitation_to_out(invitation).model_dump(), token=token, redeem_url=redeem_url
    )


@router.get("/invitations", response_model=list[ConnectionInvitationOut])
async def list_invitations_route(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[ConnectionInvitationOut]:
    invitations = await list_invitations(db, user_id=user.id, limit=limit, offset=offset)
    return [_invitation_to_out(i) for i in invitations]


@router.post(
    "/invitations/{invitation_id}/revoke",
    response_model=ConnectionInvitationOut,
    dependencies=[Depends(require_csrf)],
)
async def revoke_invitation_route(
    invitation_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ConnectionInvitationOut:
    invitation = await revoke_own_invitation(
        db, invitation_id=invitation_id, inviter_user_id=user.id
    )
    return _invitation_to_out(invitation)


@router.get("/invitations/redeem/{token}", response_model=ConnectionInvitationPreviewOut)
async def preview_invitation_route(
    token: str,
    db: AsyncSession = Depends(get_db),
) -> ConnectionInvitationPreviewOut:
    invitation = await preview_invitation(db, token=token)
    return ConnectionInvitationPreviewOut(
        method=invitation.method, expires_at=invitation.expires_at
    )


@router.post(
    "/invitations/redeem",
    response_model=RedeemInvitationResponseOut,
    status_code=201,
    dependencies=[Depends(require_csrf)],
)
async def redeem_invitation_route(
    body: RedeemInvitationRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    _rate_limit: None = Depends(
        rate_limit_by_user("connections:redeem_invitation", limit=10, window_seconds=3600)
    ),
) -> RedeemInvitationResponseOut:
    connection, workspace = await accept_invitation(db, token=body.token, redeeming_user=user)
    return RedeemInvitationResponseOut(
        connection=_connection_to_out(connection), workspace_id=workspace.id
    )


@router.post(
    "/invitations/{invitation_id}/decline",
    response_model=ConnectionInvitationOut,
    dependencies=[Depends(require_csrf)],
)
async def decline_invitation_route(
    invitation_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ConnectionInvitationOut:
    invitation = await decline_own_invitation(
        db, invitation_id=invitation_id, declining_user=user
    )
    return _invitation_to_out(invitation)


@router.get("", response_model=list[UserConnectionOut])
async def list_connections_route(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[UserConnectionOut]:
    connections = await list_connections(db, user_id=user.id, limit=limit, offset=offset)
    return [_connection_to_out(c) for c in connections]


@router.post(
    "/{connection_id}/dissolve",
    response_model=UserConnectionOut,
    dependencies=[Depends(require_csrf)],
)
async def dissolve_connection_route(
    connection_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserConnectionOut:
    connection = await dissolve_own_connection(db, connection_id=connection_id, user_id=user.id)
    return _connection_to_out(connection)
