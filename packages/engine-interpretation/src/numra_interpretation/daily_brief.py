"""V1.5 Epic K: a deterministic, reproducible "Daily Brief" -- Personal Day/Month/Year
composed into structured, knowledge-sourced reflection text.

Same non-negotiables as the rest of this package: no LLM, no network, no randomness.
Given the same `CanonicalProfile` (i.e. the same person + `as_of_date`) and the same
loaded `KnowledgeBase`, `compose_daily_brief` always returns a byte-identical result --
there is nothing time-of-day- or request-dependent in it. The composed text is
reflective/symbolic in register ("wird ... gedeutet", "beschreibt symbolisch"), never
phrased as a guaranteed future outcome; that register comes from
`knowledge/metrics/personal_*.yaml` and `knowledge/numbers/*.yaml` themselves; this
module does not add any of its own free-form language beyond what `compose_section`
already produces.
"""

from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, ConfigDict

from numra_interpretation.composer import InterpretationSection, compose_timing_sections
from numra_interpretation.knowledge_loader import KnowledgeBase
from numra_numerology.models.profile import CanonicalProfile

__all__ = ["DailyBrief", "compose_daily_brief"]


class DailyBrief(BaseModel):
    """Personal Day/Month/Year, each with its composed reflection text."""

    model_config = ConfigDict(frozen=True)

    as_of_date: dt.date
    knowledge_version: str
    sections: tuple[InterpretationSection, ...]


def compose_daily_brief(profile: CanonicalProfile, knowledge: KnowledgeBase) -> DailyBrief:
    """Compose the Daily Brief for one already-computed profile.

    Reads `profile.timing` (Personal Day/Month/Year) exactly as computed by the
    engine and `profile.timing.as_of_date` for the date it applies to -- never
    today's wall-clock date, so a caller who passed an explicit `as_of_date` when
    computing `profile` gets a brief for that date, reproducibly.
    """
    return DailyBrief(
        as_of_date=profile.timing.as_of_date,
        knowledge_version=knowledge.manifest.version,
        sections=compose_timing_sections(profile, knowledge),
    )
