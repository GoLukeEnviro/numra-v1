from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from numra_api.models import User
from numra_api.models.enums import UserRole


def normalize_email(email: str) -> str:
    """The single definition of email identity: `  Foo@Example.com ` and
    `foo@example.com` must resolve to one and the same account. Applied on the way in
    (`create_user`) and on every lookup, so the two can never drift apart."""
    return email.strip().lower()


async def create_user(db: AsyncSession, *, email: str, password_hash: str) -> User:
    user = User(email=normalize_email(email), password_hash=password_hash)
    db.add(user)
    await db.flush()
    return user


async def get_user_by_email(db: AsyncSession, *, email: str) -> User | None:
    """Compares `func.lower(User.email)` rather than the stored value directly -- the
    lookup must not depend on every existing row already having been written in
    normalized form (rows predate `create_user`'s normalization)."""
    result = await db.execute(select(User).where(func.lower(User.email) == normalize_email(email)))
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
