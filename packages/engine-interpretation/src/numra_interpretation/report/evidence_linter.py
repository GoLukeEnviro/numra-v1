"""PR-V2-11 -- Validator fuer Korrelationssprache (specs/v2/evidence-policy.md,
Abschnitt "Correlation language").

Zwei getrennte Pruefungen, absichtlich nicht zu einer verschmolzen:

1. ``lint_structured_statement`` -- strukturelle Vorbedingung. Laeuft, BEVOR ein
   Korrelations-Statement ueberhaupt ausgeliefert wird, gegen das bereits
   berechnete Ergebnis-Mapping: ohne Stichprobengroesse, Beobachtungszeitraum und
   Konfidenzkategorie darf kein Statement das Produkt verlassen ("No correlation
   statement in the product ships without sample size, observation window, and
   confidence category attached").
2. ``lint_free_text_for_causal_language`` -- Defense-in-Depth gegen kausale
   Formulierungen in beliebigem Freitext (u.a. LLM-Antworten im Copilot). Das
   strukturierte Statement aus ``numra_api.services.evidence_analysis_service``
   ist ein fester Template-String und kann diese Muster gar nicht enthalten --
   diese Pruefung existiert fuer alles, was NICHT aus diesem Template stammt.

Reine Textpruefung: kein Netzwerk, keine Datenbank, kein LLM-Import, kein
globaler Zustand -- gleiche Invariante wie ``report/linter.py``, dessen
``ReportLintResult``-Form hier bewusst gespiegelt wird."""

from __future__ import annotations

import re
from collections.abc import Mapping

__all__ = [
    "REQUIRED_QUALIFIER_FIELDS",
    "VALID_CONFIDENCE_CATEGORIES",
    "EvidenceLintResult",
    "lint_free_text_for_causal_language",
    "lint_structured_statement",
]

#: Die drei Pflicht-Qualifier aus specs/v2/evidence-policy.md. Fehlt einer davon
#: (oder ist er ``None``), ist das Statement nicht auslieferbar.
REQUIRED_QUALIFIER_FIELDS: tuple[str, ...] = (
    "sample_size",
    "observation_window_days",
    "confidence_category",
)

#: Geschlossene Menge -- identisch zu ``numra_api.models.enums.ConfidenceCategory``.
#: Hier dupliziert, weil ein Engine-Package niemals gegen ``numra_api`` importieren
#: darf; die Uebereinstimmung wird in apps/api getestet.
VALID_CONFIDENCE_CATEGORIES: frozenset[str] = frozenset(
    {"NO_RELIABLE_PATTERN", "LOW", "MEDIUM", "HIGH"}
)

#: Kausale Formulierungen, die ein Korrelationsbefund nie tragen darf
#: (specs/v2/evidence-policy.md: "Personal Day 5 verursacht hoehere Energie."
#: -- forbidden). Wortstamm-Matching mit Wortgrenzen, damit "verursachte"/
#: "verursachen" ebenfalls greifen, "Ursache" als reines Substantiv aber nicht
#: faelschlich als Kausalbehauptung gilt.
_CAUSAL_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"\bverursach\w*",
        r"\bf(ü|ue)hrt\s+zu\b",
        r"\bbewirk\w*",
        r"\bsorgt\s+f(ü|ue)r\b",
    )
)


class EvidenceLintResult:
    """Gleiche Form wie ``report.linter.ReportLintResult``: eine Fehlerliste, plus
    ``is_valid`` als abgeleitete Eigenschaft. Kein Exception-Werfen -- der Aufrufer
    entscheidet, ob ein Verstoss ein harter Fehler ist."""

    def __init__(self, errors: list[str]) -> None:
        self.errors = errors

    @property
    def is_valid(self) -> bool:
        return not self.errors


def _check_required_qualifiers(evidence_result: Mapping[str, object]) -> list[str]:
    errors: list[str] = []
    for field in REQUIRED_QUALIFIER_FIELDS:
        if field not in evidence_result:
            errors.append(f"MissingQualifier: {field!r} is absent")
        elif evidence_result[field] is None:
            errors.append(f"MissingQualifier: {field!r} is None")
    return errors


def _check_qualifier_values(evidence_result: Mapping[str, object]) -> list[str]:
    errors: list[str] = []

    for field in ("sample_size", "observation_window_days"):
        value = evidence_result.get(field)
        if isinstance(value, bool) or not isinstance(value, int):
            errors.append(f"InvalidQualifier: {field!r} must be an int, got {type(value).__name__}")
        elif value <= 0:
            errors.append(f"InvalidQualifier: {field!r} must be > 0, got {value}")

    category = evidence_result.get("confidence_category")
    if category not in VALID_CONFIDENCE_CATEGORIES:
        errors.append(
            f"InvalidQualifier: 'confidence_category' {category!r} is not one of "
            f"{sorted(VALID_CONFIDENCE_CATEGORIES)}"
        )
    return errors


def _check_statement_carries_qualifiers(evidence_result: Mapping[str, object]) -> list[str]:
    """Die Zahlen muessen im ausgelieferten Text selbst stehen, nicht nur im JSON --
    "Every such statement must display, alongside the claim: sample size,
    observation period, and uncertainty/confidence category"."""
    statement = evidence_result.get("statement_text")
    if statement is None:
        return []
    if not isinstance(statement, str) or not statement.strip():
        return ["InvalidStatement: 'statement_text' must be a non-empty string or None"]

    errors: list[str] = []
    for field in ("sample_size", "observation_window_days"):
        value = evidence_result.get(field)
        if (
            isinstance(value, int)
            and not isinstance(value, bool)
            and not re.search(rf"\b{value}\b", statement)
        ):
            errors.append(f"QualifierNotRendered: {field!r} ({value}) missing from statement")
    category = evidence_result.get("confidence_category")
    if isinstance(category, str) and category not in statement:
        errors.append(f"QualifierNotRendered: 'confidence_category' ({category}) missing")
    errors.extend(lint_free_text_for_causal_language(statement).errors)
    return errors


def lint_structured_statement(evidence_result: Mapping[str, object]) -> EvidenceLintResult:
    """Prueft ein berechnetes Evidence-Ergebnis, bevor es ausgeliefert wird.

    ``evidence_result`` ist bewusst ein ``Mapping`` und kein Pydantic-Modell: dieses
    Package kennt weder ``numra_api.schemas`` noch dessen ORM-Modelle. Erwartete
    Schluessel sind die von
    ``numra_api.services.evidence_analysis_service.compute_evidence_result``
    gelieferten.

    Fehlen die Pflichtfelder, wird nicht weiter geprueft -- Folgefehler auf
    ``None``-Werten waeren nur Rauschen."""
    missing = _check_required_qualifiers(evidence_result)
    if missing:
        return EvidenceLintResult(missing)
    errors = _check_qualifier_values(evidence_result)
    errors.extend(_check_statement_carries_qualifiers(evidence_result))
    return EvidenceLintResult(errors)


def lint_free_text_for_causal_language(text: str) -> EvidenceLintResult:
    """Findet kausale Formulierungen in beliebigem Freitext. Leerer Text ist gueltig
    (eine Antwort muss keine Behauptung enthalten)."""
    return EvidenceLintResult(
        [
            f"CausalLanguage: {match.group(0)!r} is not permitted in a correlational statement"
            for pattern in _CAUSAL_PATTERNS
            for match in pattern.finditer(text)
        ]
    )
