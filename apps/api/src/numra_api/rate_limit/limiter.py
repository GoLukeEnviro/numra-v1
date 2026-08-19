"""Fixed-window rate limiting. `RateLimiter` is a `Protocol` — callers depend only on
its shape; `InMemoryRateLimiter` (dev/test/single-instance) and `RedisRateLimiter`
(production, shared across all API instances) are interchangeable behind it. Neither
implementation is a hard security boundary (a fixed window has a well-known edge burst
at window boundaries) — this is abuse/cost protection, not an authentication control.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Protocol

from redis.asyncio import Redis

__all__ = ["InMemoryRateLimiter", "RateLimiter", "RateLimitResult", "RedisRateLimiter"]


@dataclass(frozen=True)
class RateLimitResult:
    allowed: bool
    remaining: int
    retry_after_seconds: int


class RateLimiter(Protocol):
    async def check(self, *, key: str, limit: int, window_seconds: int) -> RateLimitResult:
        """Increment the counter for ``key`` and report whether this call is still
        within ``limit`` for a ``window_seconds``-wide fixed window. Every call
        increments — callers only call this once per request they want counted."""
        ...


class InMemoryRateLimiter:
    """Process-local fixed-window counter. Correct for a single instance (matches its
    intended use: local dev and the test suite) but does not coordinate across
    multiple API processes — see `RedisRateLimiter` for that."""

    def __init__(self) -> None:
        self._counts: dict[str, tuple[int, float]] = {}
        self._lock = asyncio.Lock()

    async def check(self, *, key: str, limit: int, window_seconds: int) -> RateLimitResult:
        now = time.monotonic()
        async with self._lock:
            count, window_start = self._counts.get(key, (0, now))
            if now - window_start >= window_seconds:
                count, window_start = 0, now
            count += 1
            self._counts[key] = (count, window_start)
        retry_after = max(0, int(window_seconds - (now - window_start)))
        return RateLimitResult(
            allowed=count <= limit, remaining=max(0, limit - count), retry_after_seconds=retry_after
        )


class RedisRateLimiter:
    """Shared fixed-window counter backed by Redis (`INCR` + a one-time `EXPIRE` on the
    first increment of each window) — every API/worker instance sharing the same Redis
    sees the same counts, unlike `InMemoryRateLimiter`."""

    def __init__(self, client: Redis) -> None:
        self._client = client

    async def check(self, *, key: str, limit: int, window_seconds: int) -> RateLimitResult:
        count = await self._client.incr(key)
        if count == 1:
            await self._client.expire(key, window_seconds)
        ttl = await self._client.ttl(key)
        retry_after = ttl if isinstance(ttl, int) and ttl > 0 else window_seconds
        return RateLimitResult(
            allowed=count <= limit, remaining=max(0, limit - count), retry_after_seconds=retry_after
        )
