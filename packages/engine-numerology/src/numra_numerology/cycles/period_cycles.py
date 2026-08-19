from __future__ import annotations

from numra_numerology.cycles.segments import BirthSegments
from numra_numerology.models.cycles import PeriodCycles


def compute_period_cycles(segments: BirthSegments) -> PeriodCycles:
    """canon-spec.md §26. Values only — age-boundary transitions are RESERVED_UNFROZEN."""
    return PeriodCycles(period_1=segments.month, period_2=segments.day, period_3=segments.year)
