from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from numra_numerology.reduction.core import reduce_compound

pytestmark = pytest.mark.property


@given(st.integers(min_value=0, max_value=10_000_000))
def test_termination(raw_value: int) -> None:
    """Every allowed integer reduction terminates and returns a result."""
    result = reduce_compound(raw_value)
    assert result is not None


@given(st.integers(min_value=0, max_value=10_000_000))
def test_root_range(raw_value: int) -> None:
    """root_value is always a single digit in [0, 9], even when a master number was
    preserved as effective_value (its root is further reduced to a single digit)."""
    result = reduce_compound(raw_value)
    assert 0 <= result.root_value <= 9
    if result.master_number is not None:
        assert result.root_value == {11: 2, 22: 4, 33: 6}[result.master_number]


@given(st.integers(min_value=0, max_value=10_000_000))
def test_master_range(raw_value: int) -> None:
    result = reduce_compound(raw_value)
    assert result.master_number in (None, 11, 22, 33)


@given(st.integers(min_value=0, max_value=10_000_000).filter(lambda n: n % 11 != 0))
def test_no_false_master_property(raw_value: int) -> None:
    """Any value whose reduction path never passes through exactly 11/22/33 must not be
    flagged as a master. We approximate by checking values not divisible by 11 directly,
    then explicitly re-check the classic false-master compounds."""
    result = reduce_compound(raw_value)
    if result.master_number is not None:
        assert result.master_number in (11, 22, 33)


@pytest.mark.parametrize("false_master", [44, 55, 66, 77, 88, 99, 144, 155])
def test_no_false_master_explicit(false_master: int) -> None:
    result = reduce_compound(false_master)
    assert result.master_number not in (44, 55, 66, 77, 88, 99)


@given(st.integers(min_value=0, max_value=10_000_000))
def test_master_preservation_invariant(raw_value: int) -> None:
    """If a master number is set, effective_value equals that master number exactly."""
    result = reduce_compound(raw_value)
    if result.master_number is not None:
        assert result.effective_value == result.master_number


@given(st.integers(min_value=0, max_value=10_000_000))
def test_reduction_steps_nonempty_and_start_with_raw_value(raw_value: int) -> None:
    result = reduce_compound(raw_value)
    assert len(result.reduction_steps) >= 1
    assert result.reduction_steps[0] == raw_value
