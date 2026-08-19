from __future__ import annotations

from pydantic import BaseModel, ConfigDict

MASTER_NUMBERS: frozenset[int] = frozenset({11, 22, 33})


class MetricFlag(BaseModel):
    """A structured flag attached to a metric. Never a free-form string."""

    model_config = ConfigDict(frozen=True)

    code: str
    value: str | None = None
    source_raw_value: int | None = None


class ReductionResult(BaseModel):
    """Result of :func:`numra_numerology.reduction.core.reduce_compound`."""

    model_config = ConfigDict(frozen=True)

    source_value: int | str | None
    raw_value: int
    root_value: int
    master_number: int | None
    effective_value: int
    display_value: str
    reduction_steps: tuple[int, ...]
