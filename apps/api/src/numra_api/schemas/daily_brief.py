from __future__ import annotations

import datetime as dt

from pydantic import BaseModel


class DailyBriefSectionOut(BaseModel):
    """One Personal Day/Month/Year reflection -- knowledge-sourced, reflective
    language only, never a predictive-certainty claim (V1.5 Epic K)."""

    metric_id: str
    display_name_de: str
    display_value: str
    text_de: str


class DailyBriefOut(BaseModel):
    """Deterministic Daily Brief for one person on one `as_of_date`: identical
    inputs (person + date + knowledge version) always produce a byte-identical
    response -- there is no LLM call and no randomness anywhere in this path."""

    person_id: str
    as_of_date: dt.date
    knowledge_version: str
    sections: tuple[DailyBriefSectionOut, ...]
