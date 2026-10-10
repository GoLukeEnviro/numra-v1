from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import func, select, text, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from numra_api.models import UsageReservation
from numra_api.models.enums import BetaFeature, UsageReservationState

#: Reservations that count toward the window (a released one gave its quota back).
_COUNTED = (UsageReservationState.ACTIVE.value, UsageReservationState.SETTLED.value)


async def lock_user_feature(db: AsyncSession, *, user_id: uuid.UUID, feature: BetaFeature) -> None:
    """Serializes all reservers of one (user, feature) until the transaction ends; the
    check-then-insert below is therefore atomic per user and feature. Different users
    and features never contend."""
    await db.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
        {"key": f"usage:{user_id}:{feature.value}"},
    )


async def reservation_exists(db: AsyncSession, *, feature: BetaFeature, ref_id: uuid.UUID) -> bool:
    result = await db.execute(
        select(UsageReservation.id).where(
            UsageReservation.feature == feature.value, UsageReservation.ref_id == ref_id
        )
    )
    return result.scalar_one_or_none() is not None


async def counted_created_at(
    db: AsyncSession, *, user_id: uuid.UUID, feature: BetaFeature, since: dt.datetime
) -> list[dt.datetime]:
    """created_at of every active/settled reservation inside the window, oldest first."""
    result = await db.execute(
        select(UsageReservation.created_at)
        .where(
            UsageReservation.user_id == user_id,
            UsageReservation.feature == feature.value,
            UsageReservation.state.in_(_COUNTED),
            UsageReservation.created_at > since,
        )
        .order_by(UsageReservation.created_at)
    )
    return list(result.scalars().all())


async def count_active(
    db: AsyncSession, *, user_id: uuid.UUID, feature: BetaFeature, since: dt.datetime
) -> int:
    """Active reservations newer than ``since`` (older ones are treated as abandoned)."""
    result = await db.execute(
        select(func.count())
        .select_from(UsageReservation)
        .where(
            UsageReservation.user_id == user_id,
            UsageReservation.feature == feature.value,
            UsageReservation.state == UsageReservationState.ACTIVE.value,
            UsageReservation.created_at > since,
        )
    )
    return int(result.scalar_one())


async def insert_reservation(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    feature: BetaFeature,
    ref_id: uuid.UUID,
    state: UsageReservationState,
    now: dt.datetime,
) -> bool:
    """False if (feature, ref_id) already exists -- the DB-level idempotency guard."""
    result = await db.execute(
        pg_insert(UsageReservation)
        .values(
            user_id=user_id,
            feature=feature.value,
            ref_id=ref_id,
            state=state.value,
            created_at=now,
            finished_at=now if state != UsageReservationState.ACTIVE else None,
        )
        .on_conflict_do_nothing(constraint="uq_usage_reservations_feature_ref_id")
        .returning(UsageReservation.id)
    )
    return result.scalar_one_or_none() is not None


async def _finish(
    db: AsyncSession, *, feature: BetaFeature, ref_id: uuid.UUID, state: UsageReservationState
) -> bool:
    result = await db.execute(
        update(UsageReservation)
        .where(
            UsageReservation.feature == feature.value,
            UsageReservation.ref_id == ref_id,
            UsageReservation.state == UsageReservationState.ACTIVE.value,
        )
        .values(state=state.value, finished_at=dt.datetime.now(dt.UTC))
        .returning(UsageReservation.id)
    )
    return result.scalar_one_or_none() is not None


async def settle_reservation(db: AsyncSession, *, feature: BetaFeature, ref_id: uuid.UUID) -> bool:
    """active -> settled (work succeeded; still counts for the window). Idempotent no-op
    for unknown refs (jobs enqueued before limits were switched on)."""
    return await _finish(db, feature=feature, ref_id=ref_id, state=UsageReservationState.SETTLED)


async def release_reservation(db: AsyncSession, *, feature: BetaFeature, ref_id: uuid.UUID) -> bool:
    """active -> released (work failed terminally; the quota is given back). Idempotent."""
    return await _finish(db, feature=feature, ref_id=ref_id, state=UsageReservationState.RELEASED)
