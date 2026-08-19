"""NUMRA deterministic numerology calculation engine.

Pure Python. No network, no database, no LLM import, no global mutable state,
no randomness. See ``specs/canon-spec.md`` for the frozen calculation rules
this package implements.
"""

from __future__ import annotations

from numra_numerology.engine import calculate_profile
from numra_numerology.models.errors import (
    FutureBirthDateNotAllowed,
    NormalizationUnsupportedScript,
)
from numra_numerology.models.person import PersonInput
from numra_numerology.models.profile import CanonicalProfile

__version__ = "1.0.0"

__all__ = [
    "CanonicalProfile",
    "FutureBirthDateNotAllowed",
    "NormalizationUnsupportedScript",
    "PersonInput",
    "calculate_profile",
]
