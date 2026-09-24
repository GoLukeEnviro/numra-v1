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
    #: Bundle-level disclaimer, e.g. "Numerologie ist empirisch nicht validiert...".
    #: Optional/absent-safe -- existing manifest.yaml has no such field yet and stays
    #: valid without one.
    scientific_position: str | None = None


class AuthoringProvenance(BaseModel):
    """Who/when/what-review-state a knowledge entry's long-form content is in.

    Mirrors the predecessor project's (numerology-analyst-agent) knowledge bundle
    shape, so migrated content can carry its own provenance across unchanged.
    """

    model_config = ConfigDict(frozen=True)

    authored_at: str
    author: str
    review_status: str


class NumberKnowledge(BaseModel):
    """A single file under `knowledge/numbers/*.yaml` or `knowledge/master-numbers/*.yaml`.

    Symbolic NUMRA interpretation seed content — never a factual/scientific/diagnostic
    claim. ``strengths``/``shadows`` describe two poles of the same theme;
    ``relationships``/``work_and_creation``/``development``/``cautions`` are composed,
    consistent elaborations of that theme.

    The fields below ``cautions`` are an optional, additive long-form layer (Wave 3):
    canonical, fully-written interpretation prose alongside the short label lists
    above -- never a replacement for them. A composer reads a long-form field first
    and falls back to the corresponding short list only when the long-form field is
    absent, so existing entries without any of these fields keep working unchanged.
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

    #: Stable cross-reference id and classification, e.g. from a migrated source
    #: bundle (`de.pythagorean.v3.single.2`, `de.pythagorean.v3.master.22`).
    stable_id: str | None = None
    classification: str | None = None
    #: Which calculated metrics this entry's content applies to (e.g.
    #: "life_path_primary", "expression") -- a filter tag, not interpretation text.
    result_contexts: tuple[str, ...] = ()

    #: Canonical long-form deutungstexte (Wave 3) -- see class docstring.
    constructive_expression: str | None = None
    shadow_expression: str | None = None
    development_theme: str | None = None
    practical_suggestions: tuple[str, ...] = ()
    counter_hypotheses: tuple[str, ...] = ()
    reflection_prompts: tuple[str, ...] = ()

    #: Governance/epistemic metadata for the long-form content above.
    claim_class: str | None = None
    source_refs: tuple[str, ...] = ()
    uncertainty: str | None = None
    authoring_provenance: AuthoringProvenance | None = None


class KarmicDebtKnowledge(BaseModel):
    """A single file under `knowledge/karmic-debts/*.yaml`."""

    model_config = ConfigDict(frozen=True)

    compound: str
    themes: tuple[str, ...]

    #: Karmic debts need their own raw/reduced pair rather than reusing
    #: NumberKnowledge's value/root -- a karmic-debt entry's "value" is the
    #: pre-reduction raw number (13, 14, 16 or 19), which NumberKnowledge has no slot
    #: for at all.
    raw_value: int | None = None
    reduced_value: int | None = None

    stable_id: str | None = None
    classification: str | None = None
    result_contexts: tuple[str, ...] = ()

    constructive_expression: str | None = None
    shadow_expression: str | None = None
    development_theme: str | None = None
    practical_suggestions: tuple[str, ...] = ()
    counter_hypotheses: tuple[str, ...] = ()
    reflection_prompts: tuple[str, ...] = ()

    claim_class: str | None = None
    source_refs: tuple[str, ...] = ()
    uncertainty: str | None = None
    authoring_provenance: AuthoringProvenance | None = None


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
