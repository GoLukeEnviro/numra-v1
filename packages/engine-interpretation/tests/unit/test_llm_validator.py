from __future__ import annotations

import datetime as dt
import re

import pytest

from numra_interpretation.errors import InvalidReportSection
from numra_interpretation.llm.types import NumericClaim
from numra_interpretation.llm.validator import (
    build_metric_display_value_index,
    build_special_claim_index,
    extract_placeholder_metric_ids,
    extract_special_placeholder_ids,
    find_unauthorized_numeric_literals,
    format_hidden_passion,
    format_karmic_lessons,
    normalize_numeric_claims,
    validate_generation_result,
    validate_metric_ref_coverage,
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


def test_normalize_numeric_claims_self_heals_wrong_but_known_value(sample_profile) -> None:
    """User-approved fix (V1.6 D-2): a known metric_id with a wrong display_value must
    be silently corrected to the canonical value instead of raising -- the model
    correctly identified WHICH fact the claim is about, and the pipeline already knows
    the fact authoritatively, so there is no reason to reject the whole section over a
    mistyped literal."""
    actual = sample_profile.core_numbers.birthday.display_value
    wrong = "99/9" if actual != "99/9" else "1/1"
    claims = (NumericClaim(metric_id="birthday", display_value=wrong),)

    normalized = normalize_numeric_claims(claims, sample_profile)

    assert len(normalized) == 1
    assert normalized[0].metric_id == "birthday"
    assert normalized[0].display_value == actual


def test_normalize_numeric_claims_leaves_correct_claim_untouched(sample_profile) -> None:
    life_path = sample_profile.core_numbers.life_path.display_value
    claims = (NumericClaim(metric_id="life_path", display_value=life_path),)

    normalized = normalize_numeric_claims(claims, sample_profile)

    assert normalized == claims


def test_normalize_numeric_claims_still_raises_on_unknown_metric_id(sample_profile) -> None:
    """Preserves the hard failure for a genuinely invented id -- self-healing only
    ever corrects a mistyped *value*, never fabricates a fact for an unknown id."""
    claims = (NumericClaim(metric_id="not_a_real_metric", display_value="1"),)
    with pytest.raises(InvalidReportSection, match="Unknown metric_id"):
        normalize_numeric_claims(claims, sample_profile)


def test_metric_ref_coverage_passes_when_all_required_ids_cited() -> None:
    claims = (
        NumericClaim(metric_id="personal_year", display_value="5/5"),
        NumericClaim(metric_id="personal_month", display_value="3/3"),
        NumericClaim(metric_id="personal_day", display_value="8/8"),
    )
    validate_metric_ref_coverage(
        claims,
        ("personal_year", "personal_month", "personal_day"),
        section_id="timing",
    )  # must not raise


def test_metric_ref_coverage_passes_when_nothing_required() -> None:
    # Sections with no declared metric_refs (e.g. "cycles", "development") have
    # nothing to enforce here, regardless of what claims they carry.
    validate_metric_ref_coverage((), (), section_id="cycles")


def test_metric_ref_coverage_raises_on_missing_timing_metric() -> None:
    # Reproduces the V1.6 C production bug shape: the timing section's own
    # personal_month never got cited.
    claims = (
        NumericClaim(metric_id="personal_year", display_value="5/5"),
        NumericClaim(metric_id="personal_day", display_value="8/8"),
    )
    with pytest.raises(InvalidReportSection, match="MissingMetricCoverage") as excinfo:
        validate_metric_ref_coverage(
            claims,
            ("personal_year", "personal_month", "personal_day"),
            section_id="timing",
        )
    assert "personal_month" in str(excinfo.value)


def test_metric_ref_coverage_pinnacles_and_challenges_do_not_satisfy_timing() -> None:
    """Pinnacles/Challenges must not be able to satisfy timing coverage: a claim
    about a differently-named metric can never count toward a required id it isn't,
    even though both groups appear in the same 'cycles come before timing' section
    ordering that originally caused the production bug (a real provider recycled the
    prior Pinnacles/Challenges section's claims for the timing section instead)."""
    claims = (
        NumericClaim(metric_id="pinnacle_1", display_value="5"),
        NumericClaim(metric_id="challenge_1", display_value="2"),
    )
    with pytest.raises(InvalidReportSection, match="MissingMetricCoverage") as excinfo:
        validate_metric_ref_coverage(
            claims,
            ("personal_year", "personal_month", "personal_day"),
            section_id="timing",
        )
    message = str(excinfo.value)
    assert "personal_year" in message
    assert "personal_month" in message
    assert "personal_day" in message


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


def test_index_covers_expanded_metric_registry(sample_profile) -> None:
    """P1 numeric-claim hardening: pinnacles/challenges/subconscious_self/cornerstone/
    capstone/first_vowel/universal_year must all be citable via {{metric:ID}}, not just
    the original eight core CalculationMetric fields."""
    index = build_metric_display_value_index(sample_profile)
    for metric_id in (
        "pinnacle_1",
        "pinnacle_2",
        "pinnacle_3",
        "pinnacle_4",
        "challenge_1",
        "challenge_2",
        "challenge_3",
        "challenge_4",
        "subconscious_self",
        "cornerstone",
        "capstone",
        "first_vowel",
        "universal_year",
    ):
        assert metric_id in index
        assert index[metric_id]


def test_special_claim_index_covers_hidden_passion_and_karmic_lessons(sample_profile) -> None:
    special_index = build_special_claim_index(sample_profile)
    assert special_index["hidden_passion"] == format_hidden_passion(sample_profile)
    assert special_index["karmic_lessons"] == format_karmic_lessons(sample_profile)
    assert special_index["hidden_passion"]
    assert special_index["karmic_lessons"]


def test_extract_special_placeholder_ids_dedupes_and_preserves_order() -> None:
    text = (
        "{{special:hidden_passion}} und {{special:karmic_lessons}} und {{special:hidden_passion}}"
    )
    assert extract_special_placeholder_ids(text) == ("hidden_passion", "karmic_lessons")


def test_validate_generation_result_accepts_known_special_placeholder(sample_profile) -> None:
    text = "Deine verborgene Leidenschaft: {{special:hidden_passion}}."
    validate_generation_result(text, (), sample_profile)  # must not raise


def test_validate_generation_result_rejects_unknown_special_placeholder(sample_profile) -> None:
    text = "{{special:not_a_real_special_id}}"
    with pytest.raises(InvalidReportSection, match="Unknown special id referenced"):
        validate_generation_result(text, (), sample_profile)


def test_special_claim_validated_via_numeric_claims(sample_profile) -> None:
    """A `NumericClaim` may reference a special (non-scalar) id too — validated against
    the same merged index used by placeholder resolution."""
    hidden_passion = format_hidden_passion(sample_profile)
    claims = (NumericClaim(metric_id="hidden_passion", display_value=hidden_passion),)
    validate_numeric_claims(claims, sample_profile)  # must not raise

    wrong_claims = (NumericClaim(metric_id="hidden_passion", display_value="wrong"),)
    with pytest.raises(InvalidReportSection, match="mismatch"):
        validate_numeric_claims(wrong_claims, sample_profile)


def test_find_unauthorized_numeric_literals_detects_bare_profile_value(sample_profile) -> None:
    all_values = list(build_metric_display_value_index(sample_profile).values())
    all_values += list(build_special_claim_index(sample_profile).values())
    bare_digit = next(
        (d for value in all_values for d in re.findall(r"\d+", value) if len(d) >= 2), None
    )
    assert bare_digit is not None, "expected at least one 2+ digit value in this profile"
    text = f"Deine Lebenszahl ist buchstäblich {bare_digit}, ganz ohne Platzhalter."
    found = find_unauthorized_numeric_literals(text, sample_profile)
    assert bare_digit in found


def test_find_unauthorized_numeric_literals_ignores_placeholder_content(sample_profile) -> None:
    text = "Deine Lebenszahl ist {{metric:life_path}}."
    assert find_unauthorized_numeric_literals(text, sample_profile) == ()


def test_find_unauthorized_numeric_literals_ignores_single_digits(sample_profile) -> None:
    """Single digits 1-9 are common in ordinary prose (list items, small counts) and are
    deliberately excluded from the forbidden set — only 2+-digit runs are checked."""
    text = "Es gibt 4 Herausforderungen und 3 wichtige Themen in diesem Abschnitt."
    assert find_unauthorized_numeric_literals(text, sample_profile) == ()


def test_find_unauthorized_numeric_literals_ignores_unrelated_numbers(sample_profile) -> None:
    text = "Im Jahr 1970 begann eine neue Ära, weit weg von jeder Berechnung."
    # 1970 is not derived from any of this profile's own canonical values, so it is not
    # flagged even though it is a 4-digit number.
    assert find_unauthorized_numeric_literals(text, sample_profile) == ()
