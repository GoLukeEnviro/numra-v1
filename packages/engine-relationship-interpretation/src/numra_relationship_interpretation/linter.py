"""Provenance + forbidden-language validation for relationship/shadow-dynamics output
(specs/v2/shadow-dynamics-spec.md "Forbidden output", specs/v2/relationship-type-spec.md
"No compatibility percentage").

Extends the same linting philosophy as `numra_interpretation.report.linter` (a
pattern-matched forbidden-claim blacklist) for the two-person context -- deliberately
NOT editing that original file (MINIMAL TOUCH; `_UNSUPPORTED_CLAIM_PATTERNS` there
stays personal-report-scoped).
"""

from __future__ import annotations

import re

from numra_relationship_interpretation.errors import InvalidAnalysisSection
from numra_relationship_interpretation.schemas import ThemeStatement

__all__ = [
    "validate_no_compatibility_score",
    "validate_no_forbidden_language",
    "validate_provenance_coverage",
]

#: Diagnostic/pathologizing language forbidden in a two-person relationship context
#: (specs/v2/shadow-dynamics-spec.md: "No psychiatric diagnosis. No
#: personality-disorder language. No attachment style framed as a diagnosis.").
#: Deliberately narrower/differently-scoped than
#: `numra_interpretation.report.linter._UNSUPPORTED_CLAIM_PATTERNS` -- that list is
#: single-person-report-scoped and stays untouched.
_FORBIDDEN_DIAGNOSTIC_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"persönlichkeitsstörung",
        r"psychiatrisch\w* diagnos\w*",
        r"bindungsstil\w*.*diagnos\w*",
        r"diagnos\w*.*bindungsstil\w*",
        r"klinisch\w* diagnos\w*",
        r"medizinisch\w* diagnos\w*",
        r"borderline",
        r"narzisstisch\w* störung",
    )
)

#: A compatibility score / match percentage of any kind is forbidden
#: (specs/v2/relationship-type-spec.md "No compatibility percentage") -- matches
#: "87% kompatibel", "82/100 Kompatibilität", "match-Quote", etc.
_COMPATIBILITY_SCORE_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"\d+\s*%.*(kompatib|match|übereinstimm)",
        r"(kompatib|match|übereinstimm).*\d+\s*%",
        r"\d+\s*/\s*100.*(kompatib|match|score)",
        r"(kompatib|match|score).*\d+\s*/\s*100",
    )
)


def _all_statement_texts(*groups: tuple[ThemeStatement, ...] | ThemeStatement) -> list[str]:
    texts: list[str] = []
    for group in groups:
        if isinstance(group, ThemeStatement):
            texts.append(group.text)
        else:
            texts.extend(statement.text for statement in group)
    return texts


def validate_provenance_coverage(statements: tuple[ThemeStatement, ...]) -> None:
    """Every `ThemeStatement` needs at least one non-empty provenance category --
    `canonical_refs` or `knowledge_refs` (per specs/v2/shadow-dynamics-spec.md
    "Every theme in a generated ShadowDynamicsResult has a non-empty provenance
    category"). `workspace_evidence_refs` alone does not count in this PR, since no
    workspace-evidence source exists yet."""
    for statement in statements:
        if not statement.canonical_refs and not statement.knowledge_refs:
            raise InvalidAnalysisSection(
                "MissingProvenanceCoverage: statement has neither canonical_refs nor "
                f"knowledge_refs: {statement.text[:80]!r}"
            )


def validate_no_forbidden_language(*groups: tuple[ThemeStatement, ...] | ThemeStatement) -> None:
    """Rejects diagnostic/pathologizing language across every given statement group."""
    for text in _all_statement_texts(*groups):
        for pattern in _FORBIDDEN_DIAGNOSTIC_PATTERNS:
            if pattern.search(text):
                raise InvalidAnalysisSection(
                    f"ForbiddenDiagnosticLanguage: matched pattern {pattern.pattern!r} "
                    f"in {text[:80]!r}"
                )


def validate_no_compatibility_score(*groups: tuple[ThemeStatement, ...] | ThemeStatement) -> None:
    """Rejects any compatibility-score/match-percentage-shaped claim."""
    for text in _all_statement_texts(*groups):
        for pattern in _COMPATIBILITY_SCORE_PATTERNS:
            if pattern.search(text):
                raise InvalidAnalysisSection(
                    f"CompatibilityScoreForbidden: matched pattern {pattern.pattern!r} "
                    f"in {text[:80]!r}"
                )
