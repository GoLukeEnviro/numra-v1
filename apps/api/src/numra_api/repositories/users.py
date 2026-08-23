from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from numra_api.models import User
from numra_api.models.enums import UserRole


async def create_user(db: AsyncSession, *, email: str, password_hash: str) -> User:
    user = User(email=email, password_hash=password_hash)
    db.add(user)
    await db.flush()
    return user


async def get_user_by_email(db: AsyncSession, *, email: str) -> User | None:
    result = await db.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


async def get_user_by_email_normalized(db: AsyncSession, *, email: str) -> User | None:
    """Lowercase + strip lookup -- used only by the admin CLI (`promote-admin`), which
    accepts a human-typed email and must not fail on stray whitespace/casing. Leaves
    `get_user_by_email` (used by login, exact-match) untouched."""
    normalized = email.strip().lower()
    result = await db.execute(select(User).where(func.lower(User.email) == normalized))
    return result.scalar_one_or_none()


async def get_user_by_id(db: AsyncSession, *, user_id: uuid.UUID) -> User | None:
    return await db.get(User, user_id)


async def update_user_password(db: AsyncSession, *, user: User, password_hash: str) -> None:
    """V1.5 Epic N. Takes the already-loaded ORM `user` (never a bare id) so the
    caller has already proven ownership/authentication before this mutates anything."""
    user.password_hash = password_hash
    await db.flush()


async def set_user_role(db: AsyncSession, *, user: User, role: UserRole) -> User:
    """Admin-privileged mutation -- takes the already-loaded ORM `user` (looked up by
    id only, not user-scoped) since the caller (admin route / CLI) has already
    resolved and authorized the target."""
    user.role = role
    await db.flush()
    return user


async def set_user_active(db: AsyncSession, *, user: User, is_active: bool) -> User:
    """Admin-privileged mutation -- see `set_user_role`."""
    user.is_active = is_active
    await db.flush()
    return user
