from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict

from numra_numerology.models.cycles import Cycles
from numra_numerology.models.metric import (
    CalculationMetric,
    HiddenPassion,
    KarmicLessons,
    LetterResult,
    SubconsciousSelf,
)
from numra_numerology.models.person import BirthPlace, BirthTime
from numra_numerology.models.timing import Timing

SCHEMA_VERSION = "1.0.0"
CALCULATION_SYSTEM = "numra-canonical"
CALCULATION_VERSION = "1.0.0"


class NameNormalization(BaseModel):
    model_config = ConfigDict(frozen=True)

    original: str
    components: tuple[str, ...]
    calculation_string: str


class PersonSummary(BaseModel):
    model_config = ConfigDict(frozen=True)

    birth_first_names: str
    birth_middle_names: str | None
    birth_last_name: str
    birth_date: str
    birth_time: BirthTime | None
    birth_place: BirthPlace | None


class CoreNumbers(BaseModel):
    model_config = ConfigDict(frozen=True)

    life_path: CalculationMetric
    birthday: CalculationMetric
    attitude: CalculationMetric
    expression: CalculationMetric
    soul_urge: CalculationMetric
    personality: CalculationMetric
    maturity: CalculationMetric
    balance: CalculationMetric
    hidden_passion: HiddenPassion
    karmic_lessons: KarmicLessons
    subconscious_self: SubconsciousSelf
    cornerstone: LetterResult
    capstone: LetterResult
    first_vowel: LetterResult
    intensity_table: dict[str, int]


class Diagnostics(BaseModel):
    model_config = ConfigDict(frozen=True)

    life_path: dict[str, Any] = {}
    pinnacles: dict[str, Any] = {}


class CanonicalProfile(BaseModel):
    """Top-level NUMRA canonical calculation result. See specs/profile.schema.json."""

    model_config = ConfigDict(frozen=True)

    schema_version: str = SCHEMA_VERSION
    calculation_system: str = CALCULATION_SYSTEM
    calculation_version: str = CALCULATION_VERSION
    deterministic_hash: str | None = None

    person: PersonSummary
    normalization: NameNormalization
    core_numbers: CoreNumbers
    cycles: Cycles
    timing: Timing
    diagnostics: Diagnostics
    warnings: tuple[str, ...] = ()

    def to_canonical_json(self) -> str:
        """Byte-identical JSON for identical input+policy: sort_keys, no whitespace."""
        import json

        return json.dumps(self.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
