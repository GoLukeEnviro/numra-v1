from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict


class CalculationTrace(BaseModel):
    """Machine-truth record of how a metric was derived. Display strings are generated
    FROM this trace, never the other way around (canon-spec.md §Strings Sind Nicht Source
    Of Truth)."""

    model_config = ConfigDict(frozen=True)

    input_refs: tuple[str, ...]
    normalization: dict[str, Any] | None = None
    operations: tuple[dict[str, Any], ...]
