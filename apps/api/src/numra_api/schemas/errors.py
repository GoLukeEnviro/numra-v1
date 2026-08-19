from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class ApiError(BaseModel):
    """Explicit, structured error body. NUMRA never silently falls back — every failure
    surfaces a stable machine-readable ``code``."""

    code: str
    message: str
    detail: dict[str, Any] | None = None
