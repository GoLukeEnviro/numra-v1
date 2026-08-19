from __future__ import annotations

import datetime as dt

import pytest

from numra_interpretation.errors import InvalidReportSection
from numra_interpretation.llm.types import NumericClaim
from numra_interpretation.llm.validator import (
    build_metric_display_value_index,
    extract_placeholder_metric_ids,
    validate_generation_result,
    validate_numeric_claims,
)
from numra_numerology.engine import calculate_profile
from numra_numerology.models.person import PersonInput

pytestmark = pytest.mark.unit


@pytest.fixture(scope="module")
def sample_profile():
    person = PersonInput(
        birth_first_names="Anna",
        birth_middle_names="Marie",
        birth_last_name="Berger",
        birth_date=dt.date(1990, 3, 14),
    )
    return calculate_profile(person, as_of_date=dt.date(2026, 8, 19))


def test_index_covers_all_core_and_timing_metrics(sample_profile) -> None:
    index = build_metric_display_value_index(sample_profile)
    for metric_id in (
        "life_path",
        "birthday",
        "attitude",
        "expression",
        "soul_urge",
        "personality",
        "maturity",
        "balance",
        "personal_year",
        "personal_month",
        "personal_day",
        "universal_year",
    ):
        assert metric_id in index
        assert index[metric_id]  # non-empty display value


def test_extract_placeholder_metric_ids_dedupes_and_preserves_order() -> None:
    text = "{{metric:life_path}} und {{metric:soul_urge}} und wieder {{metric:life_path}}"
    assert extract_placeholder_metric_ids(text) == ("life_path", "soul_urge")


def test_extract_placeholder_metric_ids_empty_for_plain_text() -> None:
    assert extract_placeholder_metric_ids("keine Platzhalter hier") == ()


def test_correct_claim_passes(sample_profile) -> None:
    life_path = sample_profile.core_numbers.life_path.display_value
    claims = (NumericClaim(metric_id="life_path", display_value=life_path),)
    validate_numeric_claims(claims, sample_profile)  # must not raise


def test_wrong_claim_raises_invalid_report_section(sample_profile) -> None:
    actual = sample_profile.core_numbers.life_path.display_value
    wrong = "99/9" if actual != "99/9" else "1/1"
    claims = (NumericClaim(metric_id="life_path", display_value=wrong),)
    with pytest.raises(InvalidReportSection, match="mismatch"):
        validate_numeric_claims(claims, sample_profile)


def test_unknown_metric_id_claim_raises(sample_profile) -> None:
    claims = (NumericClaim(metric_id="not_a_real_metric", display_value="1"),)
    with pytest.raises(InvalidReportSection, match="Unknown metric_id"):
        validate_numeric_claims(claims, sample_profile)


def test_validate_generation_result_rejects_unknown_placeholder(sample_profile) -> None:
    text = "Deine Zahl ist {{metric:not_a_real_metric}}."
    with pytest.raises(InvalidReportSection, match="Unknown metric_id referenced"):
        validate_generation_result(text, (), sample_profile)


def test_validate_generation_result_accepts_known_placeholder_and_correct_claims(
    sample_profile,
) -> None:
    life_path = sample_profile.core_numbers.life_path.display_value
    text = "Deine Lebenszahl ist {{metric:life_path}}."
    claims = (NumericClaim(metric_id="life_path", display_value=life_path),)
    validate_generation_result(text, claims, sample_profile)  # must not raise


def test_validate_generation_result_rejects_placeholder_ok_but_claim_wrong(sample_profile) -> None:
    text = "Deine Lebenszahl ist {{metric:life_path}}."
    claims = (NumericClaim(metric_id="life_path", display_value="totally-wrong"),)
    with pytest.raises(InvalidReportSection, match="mismatch"):
        validate_generation_result(text, claims, sample_profile)
