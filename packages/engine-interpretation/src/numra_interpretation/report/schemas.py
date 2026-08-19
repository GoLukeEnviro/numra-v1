from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from numra_interpretation.llm.types import NumericClaim

__all__ = ["GeneratedSectionContent", "StructuredReport", "StructuredReportSection"]


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
