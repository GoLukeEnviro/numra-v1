from __future__ import annotations

import datetime as dt
from typing import NamedTuple

from numra_numerology.models.reduction import ReductionResult
from numra_numerology.reduction.core import digit_sum, reduce_compound


class BirthSegments(NamedTuple):
    month: ReductionResult
    day: ReductionResult
    year: ReductionResult


def compute_birth_segments(birth_date: dt.date) -> BirthSegments:
    """canon-spec.md §23. Month/day are reduced directly (already the 'immediate
    composite'); the year is digit-summed once first (its raw_value is the digit-sum
    compound, e.g. 1986 -> 24, not the 4-digit year itself)."""
    month = reduce_compound(birth_date.month, source_value=birth_date.month)
    day = reduce_compound(birth_date.day, source_value=birth_date.day)
    year_compound = digit_sum(birth_date.year)
    year = reduce_compound(year_compound, source_value=birth_date.year)
    return BirthSegments(month=month, day=day, year=year)
