from __future__ import annotations

import datetime as dt
import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from numra_api.deps import get_db, rate_limit_by_user, require_admin, require_csrf
from numra_api.models import User
from numra_api.models.enums import AuditAction, UserRole
from numra_api.repositories.admin import (
    compute_admin_stats,
    get_user_admin_view,
    list_users_paginated,
)
from numra_api.repositories.audit import list_audit_events_paginated, record_audit_event
from numra_api.repositories.sessions import revoke_all_sessions_for_user
from numra_api.repositories.users import get_user_by_id, set_user_active
from numra_api.schemas.admin import (
    AdminStatsOut,
    AdminUserListOut,
    AdminUserOut,
    AuditEventListOut,
)
from numra_api.services.errors import Forbidden, NotFoundError

#: Router-level gate -- every route below is admin-only by construction, not by a
#: per-route dependency that could be forgotten on a future addition.
router = APIRouter(prefix="/v1/admin", tags=["admin"], dependencies=[Depends(require_admin)])

_MAX_PAGE_SIZE = 100


@router.get("/stats", response_model=AdminStatsOut)
async def get_stats(db: AsyncSession = Depends(get_db)) -> AdminStatsOut:
    return await compute_admin_stats(db, now=dt.datetime.now(dt.UTC))


@router.get("/users", response_model=AdminUserListOut)
async def list_users(
    db: AsyncSession = Depends(get_db),
    search: str | None = Query(default=None),
    role: UserRole | None = Query(default=None),
    is_active: bool | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=_MAX_PAGE_SIZE),
) -> AdminUserListOut:
    items, total = await list_users_paginated(
        db,
        page=page,
        page_size=page_size,
        now=dt.datetime.now(dt.UTC),
        search=search,
        role=role,
        is_active=is_active,
    )
    return AdminUserListOut(items=items, total=total, page=page, page_size=page_size)


@router.get("/users/{user_id}", response_model=AdminUserOut)
async def get_user(user_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> AdminUserOut:
    view = await get_user_admin_view(db, user_id=user_id, now=dt.datetime.now(dt.UTC))
    if view is None:
        raise NotFoundError(f"user {user_id} not found")
    return view


@router.post(
    "/users/{user_id}/disable",
    status_code=204,
    dependencies=[
        Depends(require_csrf),
        Depends(rate_limit_by_user("admin:user_disable", limit=20, window_seconds=3600)),
    ],
)
async def disable_user(
    user_id: uuid.UUID,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> None:
    if user_id == admin.id:
        # This IS allowed to say why -- it's the admin's own action against their own
        # account, not an enumeration risk against someone else's.
        raise Forbidden("admins cannot disable their own account")
    target = await get_user_by_id(db, user_id=user_id)
    if target is None:
        raise NotFoundError(f"user {user_id} not found")

    now = dt.datetime.now(dt.UTC)
    await set_user_active(db, user=target, is_active=False)
    await revoke_all_sessions_for_user(db, user_id=target.id, now=now)
    await record_audit_event(
        db,
        actor_user_id=admin.id,
        action=AuditAction.USER_DISABLED,
        target_user_id=target.id,
    )


@router.post(
    "/users/{user_id}/enable",
    status_code=204,
    dependencies=[
        Depends(require_csrf),
        Depends(rate_limit_by_user("admin:user_enable", limit=20, window_seconds=3600)),
    ],
)
async def enable_user(
    user_id: uuid.UUID,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> None:
    target = await get_user_by_id(db, user_id=user_id)
    if target is None:
        raise NotFoundError(f"user {user_id} not found")

    await set_user_active(db, user=target, is_active=True)
    await record_audit_event(
        db,
        actor_user_id=admin.id,
        action=AuditAction.USER_ENABLED,
        target_user_id=target.id,
    )


@router.post(
    "/users/{user_id}/revoke-sessions",
    status_code=204,
    dependencies=[
        Depends(require_csrf),
        Depends(rate_limit_by_user("admin:user_revoke_sessions", limit=20, window_seconds=3600)),
    ],
)
async def revoke_user_sessions(
    user_id: uuid.UUID,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> None:
    target = await get_user_by_id(db, user_id=user_id)
    if target is None:
        raise NotFoundError(f"user {user_id} not found")

    await revoke_all_sessions_for_user(db, user_id=target.id, now=dt.datetime.now(dt.UTC))
    await record_audit_event(
        db,
        actor_user_id=admin.id,
        action=AuditAction.USER_SESSIONS_REVOKED,
        target_user_id=target.id,
    )


@router.get("/audit", response_model=AuditEventListOut)
async def list_audit(
    db: AsyncSession = Depends(get_db),
    action: AuditAction | None = Query(default=None),
    target_user_id: uuid.UUID | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=_MAX_PAGE_SIZE),
) -> AuditEventListOut:
    items, total = await list_audit_events_paginated(
        db, page=page, page_size=page_size, action=action, target_user_id=target_user_id
    )
    return AuditEventListOut(items=items, total=total, page=page, page_size=page_size)
