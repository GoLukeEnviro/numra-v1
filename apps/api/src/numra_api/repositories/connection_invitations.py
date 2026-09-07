from __future__ import annotations

import datetime as dt
import uuid
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from numra_api.models import ConnectionInvitation
from numra_api.models.enums import InvitationState


async def create_connection_invitation(
    db: AsyncSession, *, inviter_user_id: uuid.UUID, **fields: Any
) -> ConnectionInvitation:
    invitation = ConnectionInvitation(inviter_user_id=inviter_user_id, **fields)
    db.add(invitation)
    await db.flush()
    return invitation


async def get_invitation_for_inviter(
    db: AsyncSession, *, invitation_id: uuid.UUID, inviter_user_id: uuid.UUID
) -> ConnectionInvitation | None:
    stmt = select(ConnectionInvitation).where(
        ConnectionInvitation.id == invitation_id,
        ConnectionInvitation.inviter_user_id == inviter_user_id,
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def get_invitation_by_token_hash(
    db: AsyncSession, *, token_hash: str
) -> ConnectionInvitation | None:
    """Preview lookup (redeem-preview route) -- read-only, does not claim the token.
    See `claim_invitation_by_token_hash` for the atomic redeem path."""
    stmt = select(ConnectionInvitation).where(ConnectionInvitation.token_hash == token_hash)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def list_invitations_for_inviter(
    db: AsyncSession, *, inviter_user_id: uuid.UUID, limit: int, offset: int
) -> list[ConnectionInvitation]:
    stmt = (
        select(ConnectionInvitation)
        .where(ConnectionInvitation.inviter_user_id == inviter_user_id)
        .order_by(ConnectionInvitation.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def claim_invitation_by_token_hash(
    db: AsyncSession, *, token_hash: str, redeemed_by_user_id: uuid.UUID, now: dt.datetime
) -> ConnectionInvitation | None:
    """Atomic single-use claim -- same shape as
    repositories/verification_tokens.py::claim_verification_token
    (`UPDATE ... WHERE state='PENDING' AND expires_at>now ... RETURNING`), so a
    read-then-write race can never let the same invitation be redeemed twice
    concurrently."""
    stmt = (
        update(ConnectionInvitation)
        .where(
            ConnectionInvitation.token_hash == token_hash,
            ConnectionInvitation.state == InvitationState.PENDING,
            ConnectionInvitation.expires_at > now,
        )
        .values(
            state=InvitationState.ACCEPTED,
            redeemed_by_user_id=redeemed_by_user_id,
            redeemed_at=now,
        )
        .returning(ConnectionInvitation)
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def revoke_invitation(
    db: AsyncSession, *, invitation: ConnectionInvitation, now: dt.datetime
) -> ConnectionInvitation:
    invitation.state = InvitationState.REVOKED
    invitation.revoked_at = now
    await db.flush()
    await db.refresh(invitation)
    return invitation


async def decline_invitation(
    db: AsyncSession, *, invitation: ConnectionInvitation
) -> ConnectionInvitation:
    invitation.state = InvitationState.DECLINED
    await db.flush()
    await db.refresh(invitation)
    return invitation
