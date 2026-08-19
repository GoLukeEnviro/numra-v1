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
