from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from numra_interpretation.llm.types import NumericClaim

__all__ = [
    "GeneratedSectionContent",
    "ReportOutline",
    "ReportOutlineEntry",
    "StructuredReport",
    "StructuredReportSection",
]


class ReportOutlineEntry(BaseModel):
    """One section's planned focus, from the outline step (FULL/ULTIMATE only — see
    ``report/pipeline.py::_generate_outline``). Purely advisory context fed into that
    section's own generation call; never a source of numeric facts itself."""

    model_config = ConfigDict(frozen=True)

    section_id: str
    planned_focus: str = ""


class ReportOutline(BaseModel):
    """What the outline step asks the LLM to return: one planned focus per manifest
    section. ``entries`` defaults to empty so a provider that cannot fill a nested list
    (e.g. `MockLLMProvider`, which only knows a small set of conventional field names)
    still constructs a valid, empty outline rather than failing — the outline step is
    then a no-op for that generation, not an error."""

    model_config = ConfigDict(frozen=True)

    entries: tuple[ReportOutlineEntry, ...] = ()


class GeneratedSectionContent(BaseModel):
    """What the LLM provider is asked to return for one section. ``text`` may contain
    ``{{metric:ID}}`` placeholders; the pipeline resolves them from the Canonical
    Profile after generation — the provider never has to get the exact display value
    right itself, but any claim it does make (via ``numeric_claims``) is checked."""

    model_config = ConfigDict(frozen=True)

    #: Optional — the pipeline uses the manifest's own section title regardless (see
    #: pipeline.py), so a provider that doesn't know how to fill this (e.g. the mock)
    #: is not penalized for omitting it.
    title: str = ""
    text: str
    numeric_claims: tuple[NumericClaim, ...] = ()
    summary: str = ""


class StructuredReportSection(BaseModel):
    model_config = ConfigDict(frozen=True)

    section_id: str
    title: str
    order_index: int
    text: str
    word_count: int
    summary: str
    #: V1.5 Epic M — provenance: which CanonicalProfile metric ids and which
    #: knowledge/ entries this section was grounded in, taken verbatim from the
    #: manifest's `ReportSectionSpec` (report/manifest.py). Never inferred from the
    #: generated text itself — this is what the pipeline actually fed the model, not a
    #: guess at what the model used.
    metric_refs: tuple[str, ...] = ()
    knowledge_refs: tuple[str, ...] = ()


class StructuredReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    report_type: str
    language: str
    calculation_id: str
    calculation_version: str
    knowledge_version: str
    prompt_version: str
    model_provider: str
    model_name: str
    sections: tuple[StructuredReportSection, ...]
    total_word_count: int
