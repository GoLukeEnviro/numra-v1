"""PR-V2-11 -- verifies `compute_personal_day_for_date` matches the canon
(`calculate_profile(...).timing.personal_day`) exactly for the same inputs, and
that it stays a pure, deterministic function (no date.today(), no side effects)."""

from __future__ import annotations

import datetime as dt

import pytest

from numra_numerology.engine import calculate_profile
from numra_numerology.models.person import PersonInput
from numra_numerology.timing.lookup import (
    compute_personal_day_for_date,
    compute_personal_month_for_date,
    compute_personal_year_for_date,
)

pytestmark = pytest.mark.unit


def _person(birth_date: dt.date) -> PersonInput:
    return PersonInput(
        birth_first_names="Lukas",
        birth_last_name="Springer",
        birth_date=birth_date,
    )


def test_matches_calculate_profile_personal_day_for_same_inputs() -> None:
    birth_date = dt.date(1986, 7, 18)
    target_date = dt.date(2026, 9, 5)

    canon = calculate_profile(_person(birth_date), as_of_date=target_date)
    looked_up = compute_personal_day_for_date(birth_date, target_date)

    assert looked_up.effective_value == canon.timing.personal_day.effective_value
    assert looked_up.root_value == canon.timing.personal_day.root_value
    assert looked_up.master_number == canon.timing.personal_day.master_number
    assert looked_up.display_value == canon.timing.personal_day.display_value


@pytest.mark.parametrize(
    ("birth_date", "target_date"),
    [
        (dt.date(1990, 1, 1), dt.date(2020, 12, 31)),
        (dt.date(2001, 11, 29), dt.date(2026, 2, 28)),
        (dt.date(1975, 6, 5), dt.date(2000, 1, 1)),
    ],
)
def test_matches_calculate_profile_across_several_dates(
    birth_date: dt.date, target_date: dt.date
) -> None:
    canon = calculate_profile(_person(birth_date), as_of_date=target_date)
    looked_up = compute_personal_day_for_date(birth_date, target_date)
    assert looked_up.effective_value == canon.timing.personal_day.effective_value


def test_month_and_year_lookups_match_calculate_profile() -> None:
    """Die Evidence-Query kennt drei `correlation_target`-Werte -- alle drei Lookups
    muessen gegen denselben Kanon aufgehen, nicht nur der Personal Day."""
    birth_date = dt.date(1986, 7, 18)
    target_date = dt.date(2026, 9, 5)

    canon = calculate_profile(_person(birth_date), as_of_date=target_date)

    assert (
        compute_personal_month_for_date(birth_date, target_date).effective_value
        == canon.timing.personal_month.effective_value
    )
    assert (
        compute_personal_year_for_date(birth_date, target_date).effective_value
        == canon.timing.personal_year.effective_value
    )


def test_is_deterministic_same_inputs_same_output() -> None:
    birth_date = dt.date(1986, 7, 18)
    target_date = dt.date(2026, 9, 5)
    first = compute_personal_day_for_date(birth_date, target_date)
    second = compute_personal_day_for_date(birth_date, target_date)
    assert first == second
