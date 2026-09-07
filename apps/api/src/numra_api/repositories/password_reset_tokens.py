from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from numra_api.models import PasswordResetToken


async def create_password_reset_token(
    db: AsyncSession, *, user_id: uuid.UUID, token_hash: str, expires_at: dt.datetime
) -> PasswordResetToken:
    token = PasswordResetToken(user_id=user_id, token_hash=token_hash, expires_at=expires_at)
    db.add(token)
    await db.flush()
    return token


async def invalidate_active_password_reset_tokens_for_user(
    db: AsyncSession, *, user_id: uuid.UUID, now: dt.datetime
) -> None:
    """Called before issuing a new token (forgot-password) so an older, still-valid
    reset link stops working once a fresh one is requested."""
    await db.execute(
        update(PasswordResetToken)
        .where(
            PasswordResetToken.user_id == user_id,
            PasswordResetToken.consumed_at.is_(None),
        )
        .values(consumed_at=now)
    )


async def claim_password_reset_token(
    db: AsyncSession, *, token_hash: str, now: dt.datetime
) -> uuid.UUID | None:
    """Atomic single-use claim -- see
    `verification_tokens.claim_verification_token`'s docstring for the race this
    avoids and why an invalid/expired/consumed token is all reported as ``None``
    rather than distinguished."""
    stmt = (
        update(PasswordResetToken)
        .where(
            PasswordResetToken.token_hash == token_hash,
            PasswordResetToken.consumed_at.is_(None),
            PasswordResetToken.expires_at > now,
        )
        .values(consumed_at=now)
        .returning(PasswordResetToken.user_id)
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()
