"""FeatureFlagCache -- einfacher In-Process-TTL-Cache fuer die V2-Feature-Flags.
Kein Redis: Flags aendern sich selten (Admin-Toggle), ein kurzer TTL reicht, um die
DB nicht bei jedem Request zu treffen, waehrend `invalidate()` nach einem Admin-
Toggle eine sofortige Wirkung garantiert."""

from __future__ import annotations

import asyncio

import pytest

from numra_api.services.feature_flag_cache import FeatureFlagCache

pytestmark = pytest.mark.unit


async def test_cache_returns_stale_value_within_ttl_then_refetches() -> None:
    calls = 0

    async def fake_loader() -> dict[str, bool]:
        nonlocal calls
        calls += 1
        return {"v2_master": calls == 1}

    cache = FeatureFlagCache(loader=fake_loader, ttl_seconds=0.05)
    first = await cache.get_all()
    second = await cache.get_all()
    assert first == second  # noch im TTL-Fenster, kein zweiter Loader-Call
    assert calls == 1
    await asyncio.sleep(0.06)
    third = await cache.get_all()
    assert calls == 2
    assert third == {"v2_master": False}


async def test_invalidate_forces_refetch_before_ttl_expires() -> None:
    calls = 0

    async def fake_loader() -> dict[str, bool]:
        nonlocal calls
        calls += 1
        return {"copilot": calls == 2}

    cache = FeatureFlagCache(loader=fake_loader, ttl_seconds=10.0)
    await cache.get_all()
    assert calls == 1
    cache.invalidate()
    second = await cache.get_all()
    assert calls == 2
    assert second == {"copilot": True}
