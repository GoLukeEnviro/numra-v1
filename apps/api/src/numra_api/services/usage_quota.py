"""D4 quotas: per user and feature (report / analysis / copilot) a limit on units per
sliding window and on units in flight.

Why the database and not Redis: a reservation must commit or roll back together with the
job/message row it belongs to, and a failed job must hand its unit back exactly once. The
Redis rate limiter (`deps.rate_limit_by_user`) is a best-effort request throttle with no
such coupling -- a rolled-back job would leave its Redis count inflated. Atomicity comes
from a transaction-scoped advisory lock per (user, feature) around "count, compare,
insert": parallel requests of one user queue up on it, so with limit 5 exactly 5 of 20
simultaneous requests win. Other users and features never wait on each other.

Semantics (also in docs/ops/2026-10-10-d4-limits-and-budget.md):
* No limit configured -> `reserve` returns immediately and writes nothing.
* A unit is identified by ``ref_id`` (job id / message id). Reserving the same ref twice
  consumes once. HTTP retries with the same Idempotency-Key never reach `reserve` at all
  (the existing job is returned first); worker retries of a queued job keep the one
  reservation.
* success -> settled (counts for the window); terminal failure -> released (given back).
* A reservation still active after ``quota_active_stale_seconds`` is treated as abandoned
  (crashed process) and no longer blocks the concurrency limit.
"""

from __future__ import annotations

import datetime as dt
import math
import uuid
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from numra_api.config import Settings
from numra_api.models.enums import BetaFeature, UsageReservationState
from numra_api.repositories.usage_quota import (
    count_active,
    counted_created_at,
    insert_reservation,
    lock_user_feature,
    reservation_exists,
)
from numra_api.services.errors import QuotaExceeded

__all__ = ["GATED_RESPONSES", "QuotaLimits", "limits_for", "reserve"]

#: OpenAPI `responses=` for every route that starts cost-intensive work.
GATED_RESPONSES: dict[int | str, dict[str, str]] = {
    403: {"description": "BETA_ACCESS_REQUIRED: no individual beta grant (gate enforced)"},
    429: {
        "description": "QUOTA_EXCEEDED: per-user limit reached; "
        "see Retry-After and retry_after_seconds"
    },
}

#: Retry hint when the concurrency limit (not the window) is what blocked the request.
CONCURRENT_RETRY_AFTER_SECONDS = 30


@dataclass(frozen=True)
class QuotaLimits:
    max_per_window: int | None
    window_seconds: int
    max_concurrent: int | None

    @property
    def enabled(self) -> bool:
        return self.max_per_window is not None or self.max_concurrent is not None


def limits_for(settings: Settings, feature: BetaFeature) -> QuotaLimits:
    prefix = f"quota_{feature.value}"
    return QuotaLimits(
        max_per_window=getattr(settings, f"{prefix}_max"),
        window_seconds=getattr(settings, f"{prefix}_window_seconds"),
        max_concurrent=getattr(settings, f"{prefix}_max_concurrent"),
    )


async def reserve(
    db: AsyncSession,
    *,
    settings: Settings,
    user_id: uuid.UUID,
    feature: BetaFeature,
    ref_id: uuid.UUID,
) -> bool:
    """Reserve one unit or raise `QuotaExceeded` (429). Returns True iff this call
    consumed a unit. Caller owns the transaction; on `QuotaExceeded` nothing was written.
    """
    limits = limits_for(settings, feature)
    if not limits.enabled:
        return False

    await lock_user_feature(db, user_id=user_id, feature=feature)
    if await reservation_exists(db, feature=feature, ref_id=ref_id):
        return False

    now = dt.datetime.now(dt.UTC)
    if limits.max_per_window is not None:
        counted = await counted_created_at(
            db,
            user_id=user_id,
            feature=feature,
            since=now - dt.timedelta(seconds=limits.window_seconds),
        )
        if len(counted) >= limits.max_per_window:
            frees_at = counted[len(counted) - limits.max_per_window] + dt.timedelta(
                seconds=limits.window_seconds
            )
            raise QuotaExceeded(
                feature=feature.value,
                kind="window",
                limit=limits.max_per_window,
                retry_after_seconds=max(1, math.ceil((frees_at - now).total_seconds())),
            )
    if limits.max_concurrent is not None:
        active = await count_active(
            db,
            user_id=user_id,
            feature=feature,
            since=now - dt.timedelta(seconds=settings.quota_active_stale_seconds),
        )
        if active >= limits.max_concurrent:
            raise QuotaExceeded(
                feature=feature.value,
                kind="concurrent",
                limit=limits.max_concurrent,
                retry_after_seconds=CONCURRENT_RETRY_AFTER_SECONDS,
            )

    return await insert_reservation(
        db,
        user_id=user_id,
        feature=feature,
        ref_id=ref_id,
        state=UsageReservationState.ACTIVE,
        now=now,
    )
