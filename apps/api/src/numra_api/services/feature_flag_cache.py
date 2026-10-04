"""In-Process-TTL-Cache fuer die AVENYTH-V2-Feature-Flags. Kein Redis: Flags
aendern sich selten (Admin-Toggle via /admin/flags), ein kurzer TTL reicht, um
die DB nicht bei jedem Request zu treffen. `invalidate()` erzwingt nach einem
Admin-Toggle sofort einen frischen Read statt bis zu `ttl_seconds` zu warten."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable


class FeatureFlagCache:
    def __init__(
        self,
        loader: Callable[[], Awaitable[dict[str, bool]]],
        ttl_seconds: float = 5.0,
    ) -> None:
        self._loader = loader
        self._ttl = ttl_seconds
        self._value: dict[str, bool] | None = None
        self._loaded_at = 0.0
        self._lock = asyncio.Lock()

    async def get_all(self) -> dict[str, bool]:
        now = time.monotonic()
        if self._value is not None and (now - self._loaded_at) < self._ttl:
            return self._value
        async with self._lock:
            now = time.monotonic()
            if self._value is not None and (now - self._loaded_at) < self._ttl:
                return self._value
            self._value = await self._loader()
            self._loaded_at = now
            return self._value

    def invalidate(self) -> None:
        self._value = None
