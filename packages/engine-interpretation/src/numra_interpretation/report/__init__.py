"""The AgentWrite long-form report pipeline (master prompt §102-§113).

Canonical Profile + Knowledge -> ReportManifest -> per-section generation (with global
context carried forward) -> per-section + global validation -> StructuredReport. No
calculation logic; every numeric claim is checked against the CanonicalProfile.
"""

from __future__ import annotations

from numra_interpretation.report.linter import ReportLintResult, lint_report
from numra_interpretation.report.manifest import (
    REPORT_TYPE_WORD_RANGES,
    ReportManifest,
    ReportSectionSpec,
    build_manifest,
)
from numra_interpretation.report.pipeline import ReportGenerationError, generate_report
from numra_interpretation.report.schemas import (
    GeneratedSectionContent,
    StructuredReport,
    StructuredReportSection,
)

__all__ = [
    "REPORT_TYPE_WORD_RANGES",
    "GeneratedSectionContent",
    "ReportGenerationError",
    "ReportLintResult",
    "ReportManifest",
    "ReportSectionSpec",
    "StructuredReport",
    "StructuredReportSection",
    "build_manifest",
    "generate_report",
    "lint_report",
]
