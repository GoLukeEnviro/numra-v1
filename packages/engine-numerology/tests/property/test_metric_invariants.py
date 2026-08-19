from __future__ import annotations

import datetime as dt

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from numra_numerology.engine import calculate_profile
from numra_numerology.models.person import PersonInput

pytestmark = pytest.mark.property

_LETTERS = st.text(alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZ", min_size=1, max_size=12)
_DATES = st.dates(min_value=dt.date(1900, 1, 1), max_value=dt.date(2025, 12, 31))


@settings(max_examples=100)
@given(first=_LETTERS, last=_LETTERS, birth=_DATES)
def test_expression_invariant_holds(first: str, last: str, birth: dt.date) -> None:
    person = PersonInput(birth_first_names=first, birth_last_name=last, birth_date=birth)
    profile = calculate_profile(person, as_of_date=dt.date(2026, 1, 1))
    core = profile.core_numbers
    assert core.expression.raw_value == core.soul_urge.raw_value + core.personality.raw_value


@settings(max_examples=100)
@given(first=_LETTERS, last=_LETTERS, birth=_DATES)
def test_subconscious_karmic_invariant_holds(first: str, last: str, birth: dt.date) -> None:
    person = PersonInput(birth_first_names=first, birth_last_name=last, birth_date=birth)
    profile = calculate_profile(person, as_of_date=dt.date(2026, 1, 1))
    core = profile.core_numbers
    assert core.subconscious_self.value + len(core.karmic_lessons.values) == 9


@settings(max_examples=100)
@given(first=_LETTERS, last=_LETTERS, birth=_DATES)
def test_deterministic_hash_reproducible(first: str, last: str, birth: dt.date) -> None:
    person = PersonInput(birth_first_names=first, birth_last_name=last, birth_date=birth)
    p1 = calculate_profile(person, as_of_date=dt.date(2026, 1, 1))
    p2 = calculate_profile(person, as_of_date=dt.date(2026, 1, 1))
    assert p1.deterministic_hash == p2.deterministic_hash


@settings(max_examples=50)
@given(first=_LETTERS, last=_LETTERS, birth=_DATES)
def test_intensity_table_always_nine_keys(first: str, last: str, birth: dt.date) -> None:
    person = PersonInput(birth_first_names=first, birth_last_name=last, birth_date=birth)
    profile = calculate_profile(person, as_of_date=dt.date(2026, 1, 1))
    assert set(profile.core_numbers.intensity_table.keys()) == {str(i) for i in range(1, 10)}
