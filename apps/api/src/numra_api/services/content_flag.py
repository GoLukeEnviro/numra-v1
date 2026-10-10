"""D6: read-time verdict on stored, generated texts.

Texts stored before the token detector was hardened (#308/#315) may carry an internal
template token. Reading a single result runs the same strict detector the persistence gate
uses over a *check view* of the stored payload and reports ``content_flag``; the stored
text is never modified and never filtered out of the response.

Why computed on read and not persisted: no schema change, no backfill job, and the verdict
always follows the current detector and the current content -- a later hardening flags
more without a data migration, a manual repair of a row unflags it at once, and there is no
cache that could disagree with the database. The cost is one scan per read of a *single*
result (about 20 ms for a 64k-character report, measured), bounded by the detector's own
limits (``MAX_CHECKED_TEXT_CHARS`` per string, ``MAX_CHECKED_PAYLOAD_CHARS`` per payload;
anything above is flagged, as the gate would reject it). List endpoints do not compute it:
fifty scans per request would block the event loop, and a list card ships no content.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from numra_api.models import RelationshipAnalysis, Report
from numra_api.models.enums import ContentFlag
from numra_interpretation.llm.rendering_guard import find_unresolved_token_in_payload

__all__ = ["ReportFlags", "analysis_flag", "payload_flag", "report_flags"]


@dataclass(frozen=True)
class ReportFlags:
    content_flag: ContentFlag
    flagged_section_ids: tuple[str, ...] = ()


_NOT_FLAGGED = ReportFlags(ContentFlag.NONE)


def payload_flag(payload: object, *, strict_braces: bool) -> ContentFlag:
    """The verdict for one JSON-like payload: flagged iff the detector finds a token in any
    string value or key."""
    token = find_unresolved_token_in_payload(payload, strict_braces=strict_braces)
    return ContentFlag.NONE if token is None else ContentFlag.UNRESOLVED_TEMPLATE_TOKENS


def report_flags(report: Report) -> ReportFlags:
    """Report and per-section verdict (lenient braces: the report pipeline's mode). Sections
    are only inspected one by one when the report as a whole is flagged."""
    if report.status != "COMPLETE" or report.content_json is None:
        return _NOT_FLAGGED
    content = report.content_json
    if payload_flag(content, strict_braces=False) is ContentFlag.NONE:
        return _NOT_FLAGGED
    flagged: list[str] = []
    sections = content.get("sections")
    if isinstance(sections, list):
        for section in sections:
            if (
                isinstance(section, Mapping)
                and isinstance(section.get("section_id"), str)
                and payload_flag(section, strict_braces=False) is not ContentFlag.NONE
            ):
                flagged.append(section["section_id"])
    return ReportFlags(ContentFlag.UNRESOLVED_TEMPLATE_TOKENS, tuple(flagged))


def analysis_flag(analysis: RelationshipAnalysis) -> ContentFlag:
    """Verdict for a relationship analysis (strict braces: the analysis pipeline's mode)."""
    if analysis.status != "COMPLETE" or analysis.result_json is None:
        return ContentFlag.NONE
    return payload_flag(analysis.result_json, strict_braces=True)
