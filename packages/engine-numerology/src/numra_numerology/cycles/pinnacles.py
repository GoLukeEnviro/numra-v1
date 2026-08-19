from __future__ import annotations

import datetime as dt
from typing import Any, NamedTuple

from numra_numerology.cycles.segments import BirthSegments
from numra_numerology.models.cycles import Pinnacles, PinnacleWindow
from numra_numerology.models.reduction import ReductionResult
from numra_numerology.reduction.core import reduce_compound


class PinnacleDiagnostics(NamedTuple):
    pinnacle_1_historical: dict[str, Any]
    pinnacle_2_historical: dict[str, Any]


def compute_pinnacles(
    segments: BirthSegments,
) -> tuple[ReductionResult, ReductionResult, ReductionResult, ReductionResult]:
    """canon-spec.md §24. Contribution of P1/P2 into P3 uses effective_value, which equals
    root_value when non-master and the master number itself when master — exactly the rule
    'root if non-master, effective_value if master'."""
    p1 = reduce_compound(segments.month.effective_value + segments.day.effective_value)
    p2 = reduce_compound(segments.day.effective_value + segments.year.effective_value)
    p3 = reduce_compound(p1.effective_value + p2.effective_value)
    p4 = reduce_compound(segments.month.effective_value + segments.year.effective_value)
    return p1, p2, p3, p4


def compute_pinnacle_diagnostics(birth_date: dt.date, year_compound: int) -> PinnacleDiagnostics:
    """Historical alternative compound paths — diagnostic only, never canonical."""
    historical_1 = reduce_compound(birth_date.month + birth_date.day)
    historical_2 = reduce_compound(birth_date.day + year_compound)
    return PinnacleDiagnostics(
        pinnacle_1_historical={
            "formula": "raw_month + raw_day",
            "raw_value": historical_1.raw_value,
            "root_value": historical_1.root_value,
            "display_value": historical_1.display_value,
        },
        pinnacle_2_historical={
            "formula": "raw_day + year_compound",
            "raw_value": historical_2.raw_value,
            "root_value": historical_2.root_value,
            "display_value": historical_2.display_value,
        },
    )


def _add_years(source: dt.date, years: int) -> dt.date:
    """Add whole years to a date. Leap-day rule: Feb 29 births anniversary to Feb 28 in a
    non-leap target year (canon-spec.md §24)."""
    try:
        return source.replace(year=source.year + years)
    except ValueError:
        # source is Feb 29 and the target year is not a leap year.
        return source.replace(month=2, day=28, year=source.year + years)


def compute_pinnacle_windows(
    birth_date: dt.date, life_path_root_value: int
) -> tuple[PinnacleWindow, PinnacleWindow, PinnacleWindow, PinnacleWindow]:
    first_end_age = 36 - life_path_root_value
    bounds = [
        (0, first_end_age),
        (first_end_age + 1, first_end_age + 9),
        (first_end_age + 10, first_end_age + 18),
        (first_end_age + 19, None),
    ]
    windows: list[PinnacleWindow] = []
    for start_age, end_age in bounds:
        start_date = _add_years(birth_date, start_age)
        end_date = _add_years(birth_date, end_age + 1) if end_age is not None else None
        windows.append(
            PinnacleWindow(
                start_date=start_date, end_date=end_date, start_age=start_age, end_age=end_age
            )
        )
    return windows[0], windows[1], windows[2], windows[3]


def build_pinnacles_model(
    segments: BirthSegments, birth_date: dt.date, life_path_root_value: int
) -> Pinnacles:
    p1, p2, p3, p4 = compute_pinnacles(segments)
    windows = compute_pinnacle_windows(birth_date, life_path_root_value)
    return Pinnacles(pinnacle_1=p1, pinnacle_2=p2, pinnacle_3=p3, pinnacle_4=p4, windows=windows)
