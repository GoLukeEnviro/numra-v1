"""D4 closed-beta gate: global feature flag AND individual beta grant.

Two independent layers guard a cost-intensive feature:

1. the global runtime flag (`services/feature_flags.py`, router-level) -- the
   operator's kill switch for everybody;
2. this individual grant (`EntitlementAssignment` -> `EntitlementSet`, see
   `repositories/entitlements.py`) -- only active when ``Settings.beta_gate_enforced``.

Both must pass. A new account holds no assignment, so it passes neither automatically.
Age confirmation (`User.age_confirmed_at`, D2) is a separate property of the account and
is deliberately not consulted here -- the two checks stay independently testable.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable, Coroutine
from typing import Any

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from numra_api.config import Settings
from numra_api.deps import get_current_user, get_db, get_settings_dep
from numra_api.models import User
from numra_api.models.enums import BetaFeature
from numra_api.repositories.entitlements import user_has_beta_feature
from numra_api.services.errors import BetaAccessRequired

__all__ = ["assert_beta_access", "require_beta_access"]


async def assert_beta_access(
    db: AsyncSession, *, enforced: bool, user_id: uuid.UUID, feature: BetaFeature
) -> None:
    """Raises `BetaAccessRequired` when the gate is enforced and the user has no grant
    covering ``feature``. A no-op while the gate is off."""
    if not enforced:
        return
    if not await user_has_beta_feature(db, user_id=user_id, feature=feature):
        raise BetaAccessRequired(f"beta access required for {feature.value}")


def require_beta_access(feature: BetaFeature) -> Callable[..., Coroutine[Any, Any, None]]:
    """Per-route FastAPI dependency for the endpoints that START cost-intensive work.
    Reads stay open: a revoked user can still see what was generated for them."""

    async def _dependency(
        user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db, scope="function"),
        settings: Settings = Depends(get_settings_dep),
    ) -> None:
        await assert_beta_access(
            db, enforced=settings.beta_gate_enforced, user_id=user.id, feature=feature
        )

    return _dependency
