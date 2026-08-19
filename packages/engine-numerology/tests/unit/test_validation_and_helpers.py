from __future__ import annotations

import datetime as dt

import pytest

from numra_numerology.metrics.karmic_debt import karmic_debt_flag
from numra_numerology.metrics.name_metrics import compute_capstone, compute_cornerstone
from numra_numerology.models.errors import NoRequiredName
from numra_numerology.models.person import PersonInput

pytestmark = pytest.mark.unit


def test_empty_birth_first_names_raises() -> None:
    with pytest.raises(NoRequiredName):
        PersonInput(
            birth_first_names="   ", birth_last_name="Springer", birth_date=dt.date(1986, 7, 18)
        )


def test_empty_birth_last_name_raises() -> None:
    with pytest.raises(NoRequiredName):
        PersonInput(birth_first_names="Lukas", birth_last_name="", birth_date=dt.date(1986, 7, 18))


def test_karmic_debt_flag_ignores_metrics_outside_allowlist() -> None:
    assert karmic_debt_flag("pinnacle_3", 13, "13/4") is None


def test_karmic_debt_flag_ignores_non_matching_raw_value() -> None:
    assert karmic_debt_flag("life_path", 22, "22/4") is None


def test_cornerstone_capstone_empty_string() -> None:
    assert compute_cornerstone("").letter is None
    assert compute_capstone("").letter is None
