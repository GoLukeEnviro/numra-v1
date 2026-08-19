"""Explicit error types for the interpretation package.

NUMRA's "no silent fallback" principle applies here as much as it does in the
calculation engine: malformed knowledge content, an unresolvable metric, or an
inconsistent LLM claim must raise a clear, specific exception — never be silently
skipped, coerced, or auto-corrected.
"""

from __future__ import annotations


class KnowledgeLoadError(Exception):
    """Raised when a knowledge YAML file is missing, malformed, or fails validation.

    Always carries the offending file path in the message so failures are diagnosable
    without re-running with extra flags.
    """


class InvalidReportSection(Exception):
    """Raised by the numeric-claims validator when generated content is inconsistent
    with the Canonical Profile it is supposed to describe: an unknown ``metric_id``,
    a value mismatch, or a placeholder referencing an unknown metric. Never silently
    corrected — the caller must regenerate or reject the section.
    """
