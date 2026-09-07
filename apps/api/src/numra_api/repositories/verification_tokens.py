from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from numra_api.models import EmailVerificationToken


async def create_verification_token(
    db: AsyncSession, *, user_id: uuid.UUID, token_hash: str, expires_at: dt.datetime
) -> EmailVerificationToken:
    token = EmailVerificationToken(user_id=user_id, token_hash=token_hash, expires_at=expires_at)
    db.add(token)
    await db.flush()
    return token


async def invalidate_active_verification_tokens_for_user(
    db: AsyncSession, *, user_id: uuid.UUID, now: dt.datetime
) -> None:
    """Called before issuing a new token (request-email-verification) so an older,
    still-valid link a user requested earlier stops working once they ask again."""
    await db.execute(
        update(EmailVerificationToken)
        .where(
            EmailVerificationToken.user_id == user_id,
            EmailVerificationToken.consumed_at.is_(None),
        )
        .values(consumed_at=now)
    )


async def claim_verification_token(
    db: AsyncSession, *, token_hash: str, now: dt.datetime
) -> uuid.UUID | None:
    """Atomic single-use claim: consumes the token and returns its owning user id in
    one statement (`UPDATE ... WHERE consumed_at IS NULL ... RETURNING user_id`) so a
    read-then-write race can never let the same token be claimed twice concurrently.
    Returns ``None`` for a token that is unknown, already consumed, or expired --
    routes/auth.py maps every one of those to the same INVALID_OR_EXPIRED_TOKEN
    error, so this need not (and does not) distinguish them."""
    stmt = (
        update(EmailVerificationToken)
        .where(
            EmailVerificationToken.token_hash == token_hash,
            EmailVerificationToken.consumed_at.is_(None),
            EmailVerificationToken.expires_at > now,
        )
        .values(consumed_at=now)
        .returning(EmailVerificationToken.user_id)
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()
