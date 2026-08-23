from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import ColumnElement, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from numra_api.models import Calculation, Person, RelationshipComparison, Report, User
from numra_api.models import Session as SessionModel
from numra_api.models.enums import UserRole
from numra_api.schemas.admin import AdminStatsOut, AdminUserOut


async def _to_admin_user_out(db: AsyncSession, *, user: User, now: dt.datetime) -> AdminUserOut:
    """Builds the admin-facing view field-by-field -- never `model_validate`'d off
    the ORM object -- so `password_hash` (or any future sensitive column) can never
    leak here by accident. Per-user counts are separate correlated queries; at
    admin-console scale (dozens/hundreds of users per page) this is straightforward
    and readable, not a real bottleneck (noted as a scale-later concern)."""
    active_session_count = (
        await db.execute(
            select(func.count())
            .select_from(SessionModel)
            .where(
                SessionModel.user_id == user.id,
                SessionModel.revoked_at.is_(None),
                SessionModel.expires_at > now,
            )
        )
    ).scalar_one()
    last_login_at = (
        await db.execute(
            select(func.max(SessionModel.created_at)).where(SessionModel.user_id == user.id)
        )
    ).scalar_one_or_none()
    people_count = (
        await db.execute(select(func.count()).select_from(Person).where(Person.user_id == user.id))
    ).scalar_one()
    calculation_count = (
        await db.execute(
            select(func.count())
            .select_from(Calculation)
            .join(Person, Calculation.person_id == Person.id)
            .where(Person.user_id == user.id)
        )
    ).scalar_one()
    report_count = (
        await db.execute(select(func.count()).select_from(Report).where(Report.user_id == user.id))
    ).scalar_one()
    relationship_count = (
        await db.execute(
            select(func.count())
            .select_from(RelationshipComparison)
            .where(RelationshipComparison.user_id == user.id)
        )
    ).scalar_one()

    return AdminUserOut(
        id=str(user.id),
        email=user.email,
        role=str(user.role),
        is_active=user.is_active,
        created_at=user.created_at,
        last_login_at=last_login_at,
        active_session_count=active_session_count,
        people_count=people_count,
        calculation_count=calculation_count,
        report_count=report_count,
        relationship_count=relationship_count,
    )


async def list_users_paginated(
    db: AsyncSession,
    *,
    page: int,
    page_size: int,
    now: dt.datetime,
    search: str | None = None,
    role: UserRole | None = None,
    is_active: bool | None = None,
) -> tuple[list[AdminUserOut], int]:
    filters: list[ColumnElement[bool]] = []
    if search:
        filters.append(User.email.ilike(f"%{search}%"))
    if role is not None:
        filters.append(User.role == role)
    if is_active is not None:
        filters.append(User.is_active == is_active)

    count_stmt = select(func.count()).select_from(User)
    list_stmt = select(User).order_by(User.created_at.desc())
    if filters:
        count_stmt = count_stmt.where(*filters)
        list_stmt = list_stmt.where(*filters)
    list_stmt = list_stmt.offset((page - 1) * page_size).limit(page_size)

    total = (await db.execute(count_stmt)).scalar_one()
    users = list((await db.execute(list_stmt)).scalars().all())
    items = [await _to_admin_user_out(db, user=u, now=now) for u in users]
    return items, total


async def get_user_admin_view(
    db: AsyncSession, *, user_id: uuid.UUID, now: dt.datetime
) -> AdminUserOut | None:
    user = await db.get(User, user_id)
    if user is None:
        return None
    return await _to_admin_user_out(db, user=user, now=now)


async def compute_admin_stats(db: AsyncSession, *, now: dt.datetime) -> AdminStatsOut:
    """Real aggregate queries only -- 7/30-day windows are computed as Python
    datetimes (passed in via `now`), not raw SQL intervals."""
    seven_days_ago = now - dt.timedelta(days=7)
    thirty_days_ago = now - dt.timedelta(days=30)

    total_users = (await db.execute(select(func.count()).select_from(User))).scalar_one()
    active_users = (
        await db.execute(select(func.count()).select_from(User).where(User.is_active.is_(True)))
    ).scalar_one()
    disabled_users = (
        await db.execute(select(func.count()).select_from(User).where(User.is_active.is_(False)))
    ).scalar_one()
    registrations_last_7_days = (
        await db.execute(
            select(func.count()).select_from(User).where(User.created_at >= seven_days_ago)
        )
    ).scalar_one()
    registrations_last_30_days = (
        await db.execute(
            select(func.count()).select_from(User).where(User.created_at >= thirty_days_ago)
        )
    ).scalar_one()
    active_sessions = (
        await db.execute(
            select(func.count())
            .select_from(SessionModel)
            .where(SessionModel.revoked_at.is_(None), SessionModel.expires_at > now)
        )
    ).scalar_one()
    total_people = (await db.execute(select(func.count()).select_from(Person))).scalar_one()
    total_calculations = (
        await db.execute(select(func.count()).select_from(Calculation))
    ).scalar_one()
    total_reports = (await db.execute(select(func.count()).select_from(Report))).scalar_one()

    return AdminStatsOut(
        total_users=total_users,
        active_users=active_users,
        disabled_users=disabled_users,
        registrations_last_7_days=registrations_last_7_days,
        registrations_last_30_days=registrations_last_30_days,
        active_sessions=active_sessions,
        total_people=total_people,
        total_calculations=total_calculations,
        total_reports=total_reports,
    )
