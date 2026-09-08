from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from numra_api.models import UserConnection
from numra_api.models.enums import ConnectionStatus


async def create_user_connection(
    db: AsyncSession, *, user_a_id: uuid.UUID, user_b_id: uuid.UUID
) -> UserConnection:
    connection = UserConnection(user_a_id=user_a_id, user_b_id=user_b_id)
    db.add(connection)
    await db.flush()
    return connection


async def get_active_connection_between(
    db: AsyncSession, *, user_id: uuid.UUID, other_user_id: uuid.UUID
) -> UserConnection | None:
    """Order-independent lookup -- mirrors the DB-level LEAST/GREATEST unique index
    (models/tables.py::UserConnection) by checking both orderings explicitly."""
    stmt = select(UserConnection).where(
        UserConnection.status == ConnectionStatus.ACTIVE,
        or_(
            (UserConnection.user_a_id == user_id) & (UserConnection.user_b_id == other_user_id),
            (UserConnection.user_a_id == other_user_id) & (UserConnection.user_b_id == user_id),
        ),
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def get_connection_for_user(
    db: AsyncSession, *, connection_id: uuid.UUID, user_id: uuid.UUID
) -> UserConnection | None:
    """IDOR-safe -- filters membership (`user_a_id` or `user_b_id`) in the same
    statement as the id lookup."""
    stmt = select(UserConnection).where(
        UserConnection.id == connection_id,
        or_(UserConnection.user_a_id == user_id, UserConnection.user_b_id == user_id),
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def list_connections_for_user(
    db: AsyncSession, *, user_id: uuid.UUID, limit: int, offset: int
) -> list[UserConnection]:
    stmt = (
        select(UserConnection)
        .where(or_(UserConnection.user_a_id == user_id, UserConnection.user_b_id == user_id))
        .order_by(UserConnection.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def conditionally_dissolve_connection(
    db: AsyncSession, *, connection_id: uuid.UUID, now: dt.datetime
) -> bool:
    """Atomic `UPDATE ... WHERE id=? AND status='ACTIVE'` -- TOCTOU-safe, not a plain
    read-then-setattr-then-flush (PR-V2-10), same discipline as
    `conditionally_dissolve_workspace`. `False` means the connection was already
    DISSOLVED -- every caller treats that as an idempotent no-op."""
    stmt = (
        update(UserConnection)
        .where(UserConnection.id == connection_id, UserConnection.status == ConnectionStatus.ACTIVE)
        .values(status=ConnectionStatus.DISSOLVED, dissolved_at=now)
        .returning(UserConnection.id)
    )
    result = await db.execute(stmt)
    await db.flush()
    return result.scalar_one_or_none() is not None
