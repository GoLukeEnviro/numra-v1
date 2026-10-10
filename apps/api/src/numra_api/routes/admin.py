from __future__ import annotations

import datetime as dt
import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from numra_api.deps import (
    get_db,
    get_feature_flag_cache,
    rate_limit_by_user,
    require_admin,
    require_csrf,
)
from numra_api.models import User
from numra_api.models.enums import AuditAction, UserRole
from numra_api.repositories.admin import (
    compute_admin_stats,
    get_user_admin_view,
    list_users_paginated,
)
from numra_api.repositories.audit import list_audit_events_paginated, record_audit_event
from numra_api.repositories.entitlements import (
    BETA_ACCESS_SET_KEY,
    grant_beta_access,
    has_beta_grant,
    revoke_beta_access,
)
from numra_api.repositories.feature_flags import get_all_flags_with_metadata, set_flag
from numra_api.repositories.sessions import revoke_all_sessions_for_user
from numra_api.repositories.users import get_user_by_id, set_user_active
from numra_api.schemas.admin import (
    AdminStatsOut,
    AdminUserListOut,
    AdminUserOut,
    AuditEventListOut,
    BetaAccessOut,
    FeatureFlagListOut,
    FeatureFlagOut,
    FeatureFlagUpdateIn,
)
from numra_api.services.errors import Forbidden, NotFoundError
from numra_api.services.feature_flag_cache import FeatureFlagCache

#: Router-level gate -- every route below is admin-only by construction, not by a
#: per-route dependency that could be forgotten on a future addition.
router = APIRouter(prefix="/v1/admin", tags=["admin"], dependencies=[Depends(require_admin)])

_MAX_PAGE_SIZE = 100


@router.get("/stats", response_model=AdminStatsOut)
async def get_stats(db: AsyncSession = Depends(get_db, scope="function")) -> AdminStatsOut:
    return await compute_admin_stats(db, now=dt.datetime.now(dt.UTC))


@router.get("/users", response_model=AdminUserListOut)
async def list_users(
    db: AsyncSession = Depends(get_db, scope="function"),
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
async def get_user(
    user_id: uuid.UUID, db: AsyncSession = Depends(get_db, scope="function")
) -> AdminUserOut:
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
    db: AsyncSession = Depends(get_db, scope="function"),
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
    db: AsyncSession = Depends(get_db, scope="function"),
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
    db: AsyncSession = Depends(get_db, scope="function"),
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


@router.get("/users/{user_id}/beta-access", response_model=BetaAccessOut)
async def get_beta_access(
    user_id: uuid.UUID, db: AsyncSession = Depends(get_db, scope="function")
) -> BetaAccessOut:
    if await get_user_by_id(db, user_id=user_id) is None:
        raise NotFoundError(f"user {user_id} not found")
    return BetaAccessOut(user_id=str(user_id), granted=await has_beta_grant(db, user_id=user_id))


@router.put(
    "/users/{user_id}/beta-access",
    response_model=BetaAccessOut,
    dependencies=[
        Depends(require_csrf),
        Depends(rate_limit_by_user("admin:beta_access", limit=120, window_seconds=3600)),
    ],
)
async def grant_user_beta_access(
    user_id: uuid.UUID,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db, scope="function"),
) -> BetaAccessOut:
    """Idempotent: only the call that creates the grant writes an audit event."""
    if await get_user_by_id(db, user_id=user_id) is None:
        raise NotFoundError(f"user {user_id} not found")
    changed = await grant_beta_access(db, user_id=user_id)
    if changed:
        await record_audit_event(
            db,
            actor_user_id=admin.id,
            action=AuditAction.BETA_ACCESS_GRANTED,
            target_user_id=user_id,
            safe_metadata={"entitlement_set": BETA_ACCESS_SET_KEY, "source": "admin_api"},
        )
    return BetaAccessOut(user_id=str(user_id), granted=True, changed=changed)


@router.delete(
    "/users/{user_id}/beta-access",
    response_model=BetaAccessOut,
    dependencies=[
        Depends(require_csrf),
        Depends(rate_limit_by_user("admin:beta_access", limit=120, window_seconds=3600)),
    ],
)
async def revoke_user_beta_access(
    user_id: uuid.UUID,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db, scope="function"),
) -> BetaAccessOut:
    """Idempotent: only the call that removes the grant writes an audit event."""
    if await get_user_by_id(db, user_id=user_id) is None:
        raise NotFoundError(f"user {user_id} not found")
    changed = await revoke_beta_access(db, user_id=user_id)
    if changed:
        await record_audit_event(
            db,
            actor_user_id=admin.id,
            action=AuditAction.BETA_ACCESS_REVOKED,
            target_user_id=user_id,
            safe_metadata={"entitlement_set": BETA_ACCESS_SET_KEY, "source": "admin_api"},
        )
    return BetaAccessOut(user_id=str(user_id), granted=False, changed=changed)


@router.get("/flags", response_model=FeatureFlagListOut)
async def list_flags(db: AsyncSession = Depends(get_db, scope="function")) -> FeatureFlagListOut:
    rows = await get_all_flags_with_metadata(db)
    return FeatureFlagListOut(
        flags=[
            FeatureFlagOut(
                name=row.name,
                enabled=row.enabled,
                updated_at=row.updated_at,
                updated_by_user_id=str(row.updated_by_user_id) if row.updated_by_user_id else None,
            )
            for row in rows
        ]
    )


@router.patch(
    "/flags/{name}",
    status_code=204,
    dependencies=[
        Depends(require_csrf),
        Depends(rate_limit_by_user("admin:flag_update", limit=60, window_seconds=3600)),
    ],
)
async def update_flag(
    name: str,
    body: FeatureFlagUpdateIn,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db, scope="function"),
    cache: FeatureFlagCache = Depends(get_feature_flag_cache),
) -> None:
    await set_flag(db, name=name, enabled=body.enabled, actor_user_id=admin.id)
    cache.invalidate()


@router.get("/audit", response_model=AuditEventListOut)
async def list_audit(
    db: AsyncSession = Depends(get_db, scope="function"),
    action: AuditAction | None = Query(default=None),
    target_user_id: uuid.UUID | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=_MAX_PAGE_SIZE),
) -> AuditEventListOut:
    items, total = await list_audit_events_paginated(
        db, page=page, page_size=page_size, action=action, target_user_id=target_user_id
    )
    return AuditEventListOut(items=items, total=total, page=page, page_size=page_size)
