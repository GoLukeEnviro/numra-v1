"""Typed pydantic models for validated NUMRA knowledge content.

These models describe the *shape* of `knowledge/**/*.yaml` — they carry no calculation
logic and no defaults that would silently paper over malformed content. A file missing a
required field or carrying the wrong type fails loudly via pydantic's own
`ValidationError`, wrapped by :mod:`numra_interpretation.knowledge_loader` into a clear
:class:`KnowledgeLoadError`.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class KnowledgeManifest(BaseModel):
    """`knowledge/manifest.yaml`."""

    model_config = ConfigDict(frozen=True)

    knowledge_system: str
    version: str
    language: str


class NumberKnowledge(BaseModel):
    """A single file under `knowledge/numbers/*.yaml` or `knowledge/master-numbers/*.yaml`.

    Symbolic NUMRA interpretation seed content — never a factual/scientific/diagnostic
    claim. ``strengths``/``shadows`` describe two poles of the same theme;
    ``relationships``/``work_and_creation``/``development``/``cautions`` are composed,
    consistent elaborations of that theme.
    """

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
    """A single file under `knowledge/karmic-debts/*.yaml`."""

    model_config = ConfigDict(frozen=True)

    compound: str
    themes: tuple[str, ...]


class MetricKnowledge(BaseModel):
    """A single file under `knowledge/metrics/*.yaml`.

    Describes what a *metric* (e.g. Soul Urge vs. Life Path) means as a lens, distinct
    from what any particular number (1-9, 11/22/33) means — the two are composed together
    at interpretation time.
    """

    model_config = ConfigDict(frozen=True)

    metric_id: str
    display_name_de: str
    semantic_context_de: str
