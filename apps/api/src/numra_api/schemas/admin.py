from __future__ import annotations

import datetime as dt
from typing import Any

from pydantic import BaseModel


class AdminUserOut(BaseModel):
    """Admin-facing user view. Constructed field-by-field by the repository layer,
    never `model_validate`'d directly off the ORM object -- a future column (e.g.
    password_hash) can never leak here by accident."""

    id: str
    email: str
    role: str
    is_active: bool
    created_at: dt.datetime
    last_login_at: dt.datetime | None
    active_session_count: int
    people_count: int
    calculation_count: int
    report_count: int
    relationship_count: int


class AdminUserListOut(BaseModel):
    items: list[AdminUserOut]
    total: int
    page: int
    page_size: int


class V2HealthOut(BaseModel):
    """Same five counters as the manual SQL in
    docs/ops/2026-09-26-v2-activation-connections-workspaces.md Sec.6, now computed
    via SQLAlchemy and surfaced in the admin dashboard instead of a one-off query."""

    invitations_pending: int
    connections_active: int
    workspaces_active: int
    analysis_queued_gt_15min: int
    analysis_failed_24h: int


class AdminStatsOut(BaseModel):
    total_users: int
    active_users: int
    disabled_users: int
    registrations_last_7_days: int
    registrations_last_30_days: int
    active_sessions: int
    total_people: int
    total_calculations: int
    total_reports: int
    v2: V2HealthOut


class FeatureFlagOut(BaseModel):
    name: str
    enabled: bool
    updated_at: dt.datetime
    updated_by_user_id: str | None


class FeatureFlagListOut(BaseModel):
    flags: list[FeatureFlagOut]


class FeatureFlagUpdateIn(BaseModel):
    enabled: bool


class AuditEventOut(BaseModel):
    id: str
    actor_user_id: str | None
    action: str
    target_user_id: str | None
    safe_metadata: dict[str, Any]
    created_at: dt.datetime


class AuditEventListOut(BaseModel):
    items: list[AuditEventOut]
    total: int
    page: int
    page_size: int
