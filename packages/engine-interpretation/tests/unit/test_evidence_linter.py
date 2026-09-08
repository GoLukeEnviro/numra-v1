"""PR-V2-11 -- Korrelationssprache-Validator
(numra_interpretation/report/evidence_linter.py), specs/v2/evidence-policy.md
Acceptance check: "No correlation statement in the product ships without sample
size, observation window, and confidence category attached."
"""

from __future__ import annotations

import pytest

from numra_interpretation.report.evidence_linter import (
    REQUIRED_QUALIFIER_FIELDS,
    lint_free_text_for_causal_language,
    lint_structured_statement,
)

pytestmark = pytest.mark.unit

_VALID: dict[str, object] = {
    "sample_size": 60,
    "observation_window_days": 60,
    "confidence_category": "HIGH",
    "effect_size": 2.83,
    "baseline_mean": 3.67,
    "bucket_mean": 9.0,
    "statement_text": (
        "An den bislang beobachteten Personal-Day-5-Tagen lag deine gemessene Energie "
        "im Mittel bei 9.00 und damit hoeher als deine persoenliche Baseline von 3.67. "
        "Stichprobe: 60 Tage, Beobachtungszeitraum: 60 Tage, Konfidenz: HIGH. "
        "Das ist ein beobachteter Zusammenhang in deinen eigenen Daten, keine Ursache."
    ),
    "evidence_policy_version": 1,
}


def test_complete_statement_passes() -> None:
    assert lint_structured_statement(_VALID).is_valid


@pytest.mark.parametrize("field", REQUIRED_QUALIFIER_FIELDS)
def test_missing_qualifier_is_rejected(field: str) -> None:
    payload = {key: value for key, value in _VALID.items() if key != field}
    result = lint_structured_statement(payload)
    assert not result.is_valid
    assert any(field in error for error in result.errors)


@pytest.mark.parametrize("field", REQUIRED_QUALIFIER_FIELDS)
def test_none_qualifier_is_rejected(field: str) -> None:
    payload = {**_VALID, field: None}
    result = lint_structured_statement(payload)
    assert not result.is_valid


def test_no_reliable_pattern_payload_without_statement_passes() -> None:
    """Ein leeres Ergebnis ist gueltig -- es behauptet nichts, muss also auch nichts
    belegen."""
    payload = {
        **_VALID,
        "confidence_category": "NO_RELIABLE_PATTERN",
        "effect_size": None,
        "baseline_mean": None,
        "bucket_mean": None,
        "statement_text": None,
    }
    assert lint_structured_statement(payload).is_valid


def test_statement_that_omits_the_numbers_is_rejected() -> None:
    payload = {
        **_VALID,
        "statement_text": "Deine Energie war an Personal-Day-5-Tagen im Mittel hoeher.",
    }
    result = lint_structured_statement(payload)
    assert not result.is_valid
    assert any("QualifierNotRendered" in error for error in result.errors)


def test_unknown_confidence_category_is_rejected() -> None:
    result = lint_structured_statement({**_VALID, "confidence_category": "VERY_HIGH"})
    assert not result.is_valid


def test_zero_sample_size_is_rejected() -> None:
    result = lint_structured_statement({**_VALID, "sample_size": 0})
    assert not result.is_valid


def test_causal_statement_is_rejected_even_with_all_qualifiers() -> None:
    payload = {
        **_VALID,
        "statement_text": (
            "Personal Day 5 verursacht hoehere Energie. Stichprobe: 60 Tage, "
            "Beobachtungszeitraum: 60 Tage, Konfidenz: HIGH."
        ),
    }
    result = lint_structured_statement(payload)
    assert not result.is_valid
    assert any("CausalLanguage" in error for error in result.errors)


@pytest.mark.parametrize(
    "text",
    [
        "Personal Day 5 verursacht hoehere Energie.",
        "Ein Personal Year 8 fuehrt zu mehr Konflikten.",
        "Die Konstellation bewirkt Unruhe.",
        "Das sorgt für schlechteren Schlaf.",
        "Das sorgt fuer schlechteren Schlaf.",
    ],
)
def test_causal_free_text_is_rejected(text: str) -> None:
    assert not lint_free_text_for_causal_language(text).is_valid


@pytest.mark.parametrize(
    "text",
    [
        "",
        "An den beobachteten Tagen lag deine Energie im Mittel hoeher.",
        "Das ist ein Zusammenhang, keine Ursache.",
        "Die Beobachtung geht mit hoeherer Energie einher.",
    ],
)
def test_correlational_free_text_passes(text: str) -> None:
    assert lint_free_text_for_causal_language(text).is_valid
