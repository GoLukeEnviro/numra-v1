"""Explicit error types for the relationship/shadow-dynamics interpretation package.

Same "no silent fallback" principle as `numra_interpretation.errors`: malformed
knowledge content, an invalid analysis section, or a repair-attempt exhaustion must
raise a clear, specific exception — never be silently skipped, coerced, or
auto-corrected.
"""

from __future__ import annotations


class RelationshipKnowledgeLoadError(Exception):
    """Raised when a `knowledge/relationship-frames/**` or `knowledge/shadow-interaction/**`
    YAML file is missing, malformed, or fails validation. Always carries the offending
    file path in the message so failures are diagnosable without extra flags."""


class InvalidAnalysisSection(Exception):
    """Raised by the linter when generated content is inconsistent with what it must
    be grounded in: a `ThemeStatement` with no `canonical_refs`/`knowledge_refs`
    coverage, forbidden diagnostic language, or a compatibility-score-shaped claim.
    Never silently corrected — the caller must regenerate (one repair attempt) or
    reject the section."""


class AnalysisGenerationError(Exception):
    """Raised when the pipeline cannot produce a valid relationship/shadow-dynamics
    analysis even after the one permitted repair attempt (same pattern as
    `numra_interpretation.report.pipeline.ReportGenerationError`)."""


class ShadowInteractionRuleMissing(AnalysisGenerationError):
    """Raised by `context.assemble_shadow_context` when no `knowledge/shadow-interaction/
    rules.yaml` row covers the resolved shadow-theme pair. A permanent knowledge-content
    gap, not a transient failure -- the service layer classifies it as a terminal
    `ANALYSIS_GENERATION_ERROR` with ``retryable=False`` (a retry would hit the same
    missing row). Subclasses `AnalysisGenerationError` so it is never caught as a bare,
    unexpected exception."""
