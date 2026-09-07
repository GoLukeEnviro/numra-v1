from __future__ import annotations

import datetime as dt
import uuid

from pydantic import BaseModel

from numra_api.models.enums import ConnectionStatus, InvitationMethod, InvitationState


class ConnectionInvitationCreateRequest(BaseModel):
    method: InvitationMethod
    invitee_email: str | None = None


class ConnectionInvitationOut(BaseModel):
    id: uuid.UUID
    method: InvitationMethod
    invitee_email: str | None
    state: InvitationState
    expires_at: dt.datetime
    created_at: dt.datetime

    model_config = {"from_attributes": True}


class ConnectionInvitationCreatedOut(ConnectionInvitationOut):
    """Same shape for every EMAIL invite regardless of whether `invitee_email`
    matches an existing account (anti-enumeration, see services/connection_service.py).
    Carries the one-time plaintext `token`/`redeem_url` -- never persisted, never
    retrievable again after this response."""

    token: str
    redeem_url: str


class ConnectionInvitationPreviewOut(BaseModel):
    """Redeem-preview -- deliberately carries no PII about the inviter beyond the
    method, shown before the invitee commits to accepting."""

    method: InvitationMethod
    expires_at: dt.datetime


class RedeemInvitationRequest(BaseModel):
    token: str


class UserConnectionOut(BaseModel):
    id: uuid.UUID
    user_a_id: uuid.UUID
    user_b_id: uuid.UUID
    status: ConnectionStatus
    created_at: dt.datetime
    dissolved_at: dt.datetime | None

    model_config = {"from_attributes": True}


class RedeemInvitationResponseOut(BaseModel):
    connection: UserConnectionOut
    workspace_id: uuid.UUID
