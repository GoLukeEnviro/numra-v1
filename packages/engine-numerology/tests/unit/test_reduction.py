from __future__ import annotations

import pytest

from numra_numerology.reduction.core import reduce_compound

pytestmark = pytest.mark.unit

REDUCTION_MATRIX: list[tuple[int, str]] = [
    (0, "0"),
    (1, "1"),
    (9, "9"),
    (10, "10/1"),
    (11, "11/2"),
    (12, "12/3"),
    (13, "13/4"),
    (19, "19/1"),
    (22, "22/4"),
    (29, "11/2"),
    (33, "33/6"),
    (38, "11/2"),
    (44, "44/8"),
    (55, "55/1"),
    (99, "99/9"),
]


@pytest.mark.parametrize("raw_value,expected_display", REDUCTION_MATRIX)
def test_reduction_matrix(raw_value: int, expected_display: str) -> None:
    result = reduce_compound(raw_value)
    assert result.display_value == expected_display


def test_zero() -> None:
    result = reduce_compound(0)
    assert result.raw_value == 0
    assert result.root_value == 0
    assert result.master_number is None
    assert result.effective_value == 0
    assert result.display_value == "0"
    assert result.reduction_steps == (0,)


def test_negative_raises() -> None:
    with pytest.raises(ValueError):
        reduce_compound(-1)


def test_master_44_is_not_a_master() -> None:
    result = reduce_compound(44)
    assert result.master_number is None
    assert result.effective_value == 8
    assert result.display_value == "44/8"


@pytest.mark.parametrize("false_master", [44, 55, 66, 77, 88, 99])
def test_no_false_masters(false_master: int) -> None:
    result = reduce_compound(false_master)
    assert result.master_number is None


def test_master_preservation_effective_value() -> None:
    for master in (11, 22, 33):
        result = reduce_compound(master)
        assert result.master_number == master
        assert result.effective_value == master


def test_29_reduces_via_11_not_original_raw_in_display() -> None:
    result = reduce_compound(29)
    assert result.raw_value == 29
    assert result.reduction_steps == (29, 11)
    assert result.display_value == "11/2"
    assert result.master_number == 11


def test_source_value_is_independent_of_raw_value() -> None:
    result = reduce_compound(24, source_value=1986)
    assert result.source_value == 1986
    assert result.raw_value == 24
    assert result.display_value == "24/6"
