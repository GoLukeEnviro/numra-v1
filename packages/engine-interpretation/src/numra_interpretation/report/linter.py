"""The global Report Linter (master prompt §109). Runs after section assembly.

Only PASS unlocks ``REPORT_STATUS=VALID``. Every check here is a structural/textual
check on the *assembled* report — the per-claim numeric linter (validator.py) already
ran once per section during generation; `numerical_consistency` here re-runs it across
the whole assembled report as a final guard.
"""

from __future__ import annotations

import re

from numra_interpretation.llm.validator import (
    build_metric_display_value_index,
    extract_placeholder_metric_ids,
)
from numra_interpretation.report.manifest import ReportManifest
from numra_interpretation.report.schemas import StructuredReportSection
from numra_numerology.models.profile import CanonicalProfile

__all__ = ["ReportLintResult", "lint_report"]

#: Language a symbolic interpretation system must never use (master prompt §108).
#: Deliberately conservative/short — a real deployment would extend this via the
#: `numerology_safety`-equivalent claims blacklist; NUMRA V1 checks the core cases here.
_UNSUPPORTED_CLAIM_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"wissenschaftlich (bewiesen|belegt)",
        r"medizinisch(e)? diagnos\w*",
        r"garantiert\w*",
        r"heilt\b",
        r"psychiatrisch\w* diagnos\w*",
    )
)

_PLACEHOLDER_PATTERN = re.compile(r"\{\{\s*metric\s*:\s*[a-zA-Z0-9_]+\s*\}\}")


class ReportLintResult:
    def __init__(self, errors: list[str]) -> None:
        self.errors = errors

    @property
    def is_valid(self) -> bool:
        return not self.errors


def _check_missing_sections(
    manifest: ReportManifest, sections: tuple[StructuredReportSection, ...]
) -> list[str]:
    expected = {spec.section_id for spec in manifest.sections}
    actual = {section.section_id for section in sections}
    missing = expected - actual
    return [f"MissingSections: {sid}" for sid in sorted(missing)]


def _check_duplicate_headings(sections: tuple[StructuredReportSection, ...]) -> list[str]:
    seen: dict[str, int] = {}
    errors = []
    for section in sections:
        seen[section.title] = seen.get(section.title, 0) + 1
    for title, count in seen.items():
        if count > 1:
            errors.append(f"DuplicateHeadings: {title!r} appears {count} times")
    return errors


def _check_duplicate_paragraphs(sections: tuple[StructuredReportSection, ...]) -> list[str]:
    seen: dict[str, str] = {}
    errors = []
    for section in sections:
        for paragraph in section.text.split("\n\n"):
            normalized = paragraph.strip()
            if len(normalized.split()) < 12:  # ignore short/boilerplate lines
                continue
            if normalized in seen and seen[normalized] != section.section_id:
                errors.append(
                    f"DuplicateParagraphDetection: identical paragraph in "
                    f"{seen[normalized]!r} and {section.section_id!r}"
                )
            else:
                seen[normalized] = section.section_id
    return errors


#: Flat allowance added to the upper bound on top of the proportional tolerance. A
#: provider's structured response carries some fixed overhead (framing, citations,
#: transitions) independent of the target length — this is most visible for small
#: (QUICK-report-scale) targets, where fixed overhead can exceed the target itself.
#: This check exists to catch sections that are wildly off (empty, or absurdly long),
#: not to enforce prose-quality word-count precision that only a real LLM could hit.
_WORD_COUNT_FLAT_ALLOWANCE = 250


def _check_word_counts(
    manifest: ReportManifest, sections: tuple[StructuredReportSection, ...], tolerance: float
) -> list[str]:
    specs_by_id = {spec.section_id: spec for spec in manifest.sections}
    errors = []
    for section in sections:
        spec = specs_by_id.get(section.section_id)
        if spec is None:
            continue
        low = spec.target_word_count * (1 - tolerance)
        high = spec.target_word_count * (1 + tolerance) + _WORD_COUNT_FLAT_ALLOWANCE
        if not (low <= section.word_count <= high):
            errors.append(
                f"WordCountValidation: section {section.section_id!r} has "
                f"{section.word_count} words, expected ~{spec.target_word_count} "
                f"(tolerance {tolerance:.0%} + {_WORD_COUNT_FLAT_ALLOWANCE} flat)"
            )
    return errors


def _check_placeholder_resolution(sections: tuple[StructuredReportSection, ...]) -> list[str]:
    errors = []
    for section in sections:
        if _PLACEHOLDER_PATTERN.search(section.text):
            errors.append(
                f"PlaceholderResolution: unresolved placeholder in {section.section_id!r}"
            )
    return errors


def _check_unsupported_claims(sections: tuple[StructuredReportSection, ...]) -> list[str]:
    errors = []
    for section in sections:
        for pattern in _UNSUPPORTED_CLAIM_PATTERNS:
            if pattern.search(section.text):
                errors.append(
                    f"UnsupportedClaims: section {section.section_id!r} matched "
                    f"forbidden pattern {pattern.pattern!r}"
                )
    return errors


def _check_numerical_consistency(
    sections: tuple[StructuredReportSection, ...], profile: CanonicalProfile
) -> list[str]:
    index = build_metric_display_value_index(profile)
    errors = []
    for section in sections:
        for metric_id in extract_placeholder_metric_ids(section.text):
            if metric_id not in index:
                errors.append(
                    f"MetricReferenceIntegrity: unknown metric_id {metric_id!r} in "
                    f"{section.section_id!r}"
                )
    return errors


def lint_report(
    manifest: ReportManifest,
    sections: tuple[StructuredReportSection, ...],
    profile: CanonicalProfile,
    *,
    word_count_tolerance: float = 0.5,
) -> ReportLintResult:
    errors: list[str] = []
    errors += _check_missing_sections(manifest, sections)
    errors += _check_duplicate_headings(sections)
    errors += _check_duplicate_paragraphs(sections)
    errors += _check_word_counts(manifest, sections, word_count_tolerance)
    errors += _check_placeholder_resolution(sections)
    errors += _check_unsupported_claims(sections)
    errors += _check_numerical_consistency(sections, profile)
    return ReportLintResult(errors)
