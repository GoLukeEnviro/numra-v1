from __future__ import annotations

import datetime as dt
import uuid

from pydantic import BaseModel

from numra_api.models.enums import ConsentScope


class ConsentGrantRequest(BaseModel):
    scope: ConsentScope


class ConsentRevokeRequest(BaseModel):
    scope: ConsentScope


class ConsentGrantOut(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    grantor_user_id: uuid.UUID
    grantee_user_id: uuid.UUID
    scope: ConsentScope
    version: int
    granted_at: dt.datetime
    revoked_at: dt.datetime | None

    model_config = {"from_attributes": True}


class WorkspaceConsentOut(BaseModel):
    """Split by direction -- `granted_by_me` are grants where the caller is the
    grantor, `granted_to_me` where the caller is the grantee."""

    granted_by_me: list[ConsentGrantOut]
    granted_to_me: list[ConsentGrantOut]
