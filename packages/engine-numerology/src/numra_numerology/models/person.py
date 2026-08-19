from __future__ import annotations

import datetime as dt
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, model_validator


class BirthTimePrecision(StrEnum):
    EXACT = "exact"
    APPROXIMATE = "approximate"
    UNKNOWN = "unknown"


class BirthTime(BaseModel):
    """METADATA_ONLY — never affects a Core numerology metric in V1."""

    model_config = ConfigDict(frozen=True)

    value: dt.time | None = None
    precision: BirthTimePrecision = BirthTimePrecision.UNKNOWN


class BirthPlace(BaseModel):
    """METADATA_ONLY — no geocoding happens inside this package."""

    model_config = ConfigDict(frozen=True)

    display_name: str
    country_code: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    timezone: str | None = None


class PersonInput(BaseModel):
    """Raw person input as supplied by a caller, before normalization."""

    model_config = ConfigDict(frozen=True)

    birth_first_names: str
    birth_middle_names: str | None = None
    birth_last_name: str
    birth_date: dt.date

    birth_time: BirthTime | None = None
    birth_place: BirthPlace | None = None

    current_first_names: str | None = None
    current_middle_names: str | None = None
    current_last_name: str | None = None
    preferred_name: str | None = None

    @model_validator(mode="after")
    def _require_birth_names(self) -> PersonInput:
        from numra_numerology.models.errors import NoRequiredName

        if not self.birth_first_names.strip():
            raise NoRequiredName("birth_first_names is required and must be non-empty")
        if not self.birth_last_name.strip():
            raise NoRequiredName("birth_last_name is required and must be non-empty")
        return self

    @property
    def full_birth_name(self) -> str:
        """Birth first + middle + last names, in that order, space-joined — the basis for
        the full-name Core metrics (Expression, Soul Urge, Personality, ...)."""
        parts = [self.birth_first_names]
        if self.birth_middle_names:
            parts.append(self.birth_middle_names)
        parts.append(self.birth_last_name)
        return " ".join(parts)
