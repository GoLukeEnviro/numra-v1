from __future__ import annotations

import pytest

from numra_relationship_interpretation.errors import InvalidAnalysisSection
from numra_relationship_interpretation.linter import (
    validate_no_compatibility_score,
    validate_no_forbidden_language,
    validate_provenance_coverage,
)
from numra_relationship_interpretation.schemas import ThemeStatement

pytestmark = pytest.mark.unit


def test_provenance_coverage_passes_with_canonical_refs() -> None:
    statement = ThemeStatement(text="x", canonical_refs=("metric:a:life_path",))
    validate_provenance_coverage((statement,))


def test_provenance_coverage_passes_with_knowledge_refs() -> None:
    statement = ThemeStatement(
        text="x", knowledge_refs=("relationship-frames/PARTNER#communication",)
    )
    validate_provenance_coverage((statement,))


def test_provenance_coverage_fails_when_both_empty() -> None:
    statement = ThemeStatement(text="x")
    with pytest.raises(InvalidAnalysisSection):
        validate_provenance_coverage((statement,))


@pytest.mark.parametrize(
    "text",
    [
        "Das deutet auf eine Persönlichkeitsstörung hin.",
        "Eine psychiatrische Diagnose wäre hier angebracht.",
        "Der Bindungsstil ist klar diagnostizierbar.",
        "Das zeigt klinisch diagnostizierte Muster.",
    ],
)
def test_forbidden_diagnostic_language_rejected(text: str) -> None:
    statement = ThemeStatement(text=text, canonical_refs=("x",))
    with pytest.raises(InvalidAnalysisSection):
        validate_no_forbidden_language(statement)


def test_non_diagnostic_attachment_reflection_allowed() -> None:
    statement = ThemeStatement(
        text="Die Bindungsbedürfnisse zeigen sich als Wunsch nach Verlässlichkeit.",
        canonical_refs=("x",),
    )
    validate_no_forbidden_language(statement)


@pytest.mark.parametrize(
    "text",
    [
        "Die beiden sind zu 87% kompatibel.",
        "Kompatibilität: 82/100.",
        "Eine hohe Match-Quote von 91% zeigt sich.",
    ],
)
def test_compatibility_score_rejected(text: str) -> None:
    statement = ThemeStatement(text=text, canonical_refs=("x",))
    with pytest.raises(InvalidAnalysisSection):
        validate_no_compatibility_score(statement)


def test_ordinary_percentage_not_about_compatibility_is_allowed() -> None:
    statement = ThemeStatement(
        text="In 50% der beobachteten Fälle war die Stimmung ausgeglichen.",
        canonical_refs=("x",),
    )
    validate_no_compatibility_score(statement)
