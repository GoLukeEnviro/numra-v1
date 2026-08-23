from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from numra_api.models import Session as SessionModel


async def create_session(
    db: AsyncSession, *, user_id: uuid.UUID, token_hash: str, expires_at: dt.datetime
) -> SessionModel:
    session = SessionModel(user_id=user_id, token_hash=token_hash, expires_at=expires_at)
    db.add(session)
    await db.flush()
    return session


async def get_active_session_by_token_hash(
    db: AsyncSession, *, token_hash: str, now: dt.datetime
) -> SessionModel | None:
    stmt = select(SessionModel).where(
        SessionModel.token_hash == token_hash,
        SessionModel.revoked_at.is_(None),
        SessionModel.expires_at > now,
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def revoke_session(db: AsyncSession, *, token_hash: str, now: dt.datetime) -> None:
    await db.execute(
        update(SessionModel).where(SessionModel.token_hash == token_hash).values(revoked_at=now)
    )


async def list_active_sessions_for_user(
    db: AsyncSession, *, user_id: uuid.UUID, now: dt.datetime
) -> list[SessionModel]:
    """V1.5 Epic N — every session the user could currently log out of, newest
    first. Ownership-scoped via `user_id` in the query itself, never trusting a
    caller-supplied id alone."""
    stmt = (
        select(SessionModel)
        .where(
            SessionModel.user_id == user_id,
            SessionModel.revoked_at.is_(None),
            SessionModel.expires_at > now,
        )
        .order_by(SessionModel.created_at.desc())
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def revoke_all_sessions_except(
    db: AsyncSession, *, user_id: uuid.UUID, keep_token_hash: str, now: dt.datetime
) -> None:
    """V1.5 Epic N — "log out other devices" and the automatic revocation on
    password change both use this: every other active session for this user is
    revoked, the caller's own (current) session is left untouched."""
    await db.execute(
        update(SessionModel)
        .where(
            SessionModel.user_id == user_id,
            SessionModel.token_hash != keep_token_hash,
            SessionModel.revoked_at.is_(None),
        )
        .values(revoked_at=now)
    )


async def revoke_all_sessions_for_user(
    db: AsyncSession, *, user_id: uuid.UUID, now: dt.datetime
) -> None:
    """Admin-forced disable: revokes every active session for this user, no
    keep-token (unlike `revoke_all_sessions_except`, which always preserves the
    caller's own session -- there is no "caller's own session" in an admin action
    against someone else's account)."""
    await db.execute(
        update(SessionModel)
        .where(
            SessionModel.user_id == user_id,
            SessionModel.revoked_at.is_(None),
        )
        .values(revoked_at=now)
    )
