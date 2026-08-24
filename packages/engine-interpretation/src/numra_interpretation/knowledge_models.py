"""Typed pydantic models for validated NUMRA knowledge content."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class KnowledgeManifest(BaseModel):
    model_config = ConfigDict(frozen=True)

    knowledge_system: str
    version: str
    language: str


class NumberKnowledge(BaseModel):
    model_config = ConfigDict(frozen=True)

    value: int
    root: int
    is_master: bool
    core_themes: tuple[str, ...]
    strengths: tuple[str, ...]
    shadows: tuple[str, ...]
    relationships: tuple[str, ...]
    work_and_creation: tuple[str, ...]
    development: tuple[str, ...]
    cautions: tuple[str, ...]


class KarmicDebtKnowledge(BaseModel):
    model_config = ConfigDict(frozen=True)

    compound: str
    themes: tuple[str, ...]


class MetricKnowledge(BaseModel):
    model_config = ConfigDict(frozen=True)

    metric_id: str
    display_name_de: str
    semantic_context_de: str
    meaning_paragraph_de: str = Field(
        default="",
        description="Optionaler Absatz: was diese Metrik als Linse bedeutet.",
    )
