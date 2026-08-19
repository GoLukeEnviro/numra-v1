from __future__ import annotations

import asyncio

import pytest
from redis.asyncio import from_url

from numra_api.rate_limit.keys import pseudonymous_key
from numra_api.rate_limit.limiter import InMemoryRateLimiter, RedisRateLimiter

pytestmark = pytest.mark.unit


async def test_in_memory_allows_up_to_limit_then_blocks() -> None:
    limiter = InMemoryRateLimiter()
    results = [await limiter.check(key="k", limit=3, window_seconds=60) for _ in range(4)]
    assert [r.allowed for r in results] == [True, True, True, False]
    assert results[-1].retry_after_seconds > 0


async def test_in_memory_keys_are_independent() -> None:
    limiter = InMemoryRateLimiter()
    for _ in range(3):
        assert (await limiter.check(key="a", limit=3, window_seconds=60)).allowed
    # A different key starts its own fresh window.
    assert (await limiter.check(key="b", limit=3, window_seconds=60)).allowed


async def test_in_memory_window_resets_after_expiry() -> None:
    limiter = InMemoryRateLimiter()
    for _ in range(2):
        assert (await limiter.check(key="k", limit=2, window_seconds=0)).allowed
    # window_seconds=0 means every call is already past the window boundary.
    assert (await limiter.check(key="k", limit=2, window_seconds=0)).allowed


def test_pseudonymous_key_does_not_reveal_raw_identity() -> None:
    key = pseudonymous_key("198.51.100.7", secret="s3cr3t")
    assert "198.51.100.7" not in key
    assert len(key) == 32


def test_pseudonymous_key_is_deterministic_and_secret_scoped() -> None:
    assert pseudonymous_key("same-input", secret="secret-a") == pseudonymous_key(
        "same-input", secret="secret-a"
    )
    assert pseudonymous_key("same-input", secret="secret-a") != pseudonymous_key(
        "same-input", secret="secret-b"
    )


@pytest.fixture
async def redis_client():
    client = from_url("redis://127.0.0.1:6379/15")  # dedicated test DB index
    await client.flushdb()
    yield client
    await client.flushdb()
    await client.aclose()


async def test_redis_limiter_allows_up_to_limit_then_blocks(redis_client) -> None:
    limiter = RedisRateLimiter(redis_client)
    key = "test:redis-limiter"
    results = [await limiter.check(key=key, limit=3, window_seconds=60) for _ in range(4)]
    assert [r.allowed for r in results] == [True, True, True, False]
    assert results[-1].retry_after_seconds > 0


async def test_redis_limiter_keys_are_independent(redis_client) -> None:
    limiter = RedisRateLimiter(redis_client)
    for _ in range(3):
        assert (await limiter.check(key="redis-a", limit=3, window_seconds=60)).allowed
    assert (await limiter.check(key="redis-b", limit=3, window_seconds=60)).allowed


async def test_redis_limiter_shared_across_instances(redis_client) -> None:
    """Unlike InMemoryRateLimiter, two separate RedisRateLimiter objects (standing in
    for two separate API process instances) sharing the same Redis must see the same
    counter -- this is the whole point of the Redis backend."""
    limiter_instance_a = RedisRateLimiter(redis_client)
    limiter_instance_b = RedisRateLimiter(from_url("redis://127.0.0.1:6379/15"))
    key = "test:shared-across-instances"
    try:
        for _ in range(3):
            assert (await limiter_instance_a.check(key=key, limit=5, window_seconds=60)).allowed
        for _ in range(2):
            assert (await limiter_instance_b.check(key=key, limit=5, window_seconds=60)).allowed
        # The 6th increment total (3 via A, 2 via B, this one via A) must now be blocked.
        assert not (await limiter_instance_a.check(key=key, limit=5, window_seconds=60)).allowed
    finally:
        await limiter_instance_b._client.aclose()


async def test_redis_limiter_window_expires(redis_client) -> None:
    limiter = RedisRateLimiter(redis_client)
    key = "test:redis-window-expiry"
    assert (await limiter.check(key=key, limit=1, window_seconds=1)).allowed
    assert not (await limiter.check(key=key, limit=1, window_seconds=1)).allowed
    await asyncio.sleep(1.2)
    assert (await limiter.check(key=key, limit=1, window_seconds=1)).allowed
