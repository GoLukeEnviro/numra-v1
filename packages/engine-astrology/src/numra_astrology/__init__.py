"""NUMRA astrology engine interface.

STATUS: FEATURE_DISABLED_NO_CANON

No astrological calculation is implemented or exposed as available in NUMRA V1.
This module exists so that ``CanonicalPerson`` metadata (birth date/time/place,
timezone, coordinates) can later be handed to a real astrology engine once a
separate, verified canon exists for it.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel


class AstrologyFeatureStatus(str, Enum):
    FEATURE_DISABLED_NO_CANON = "FEATURE_DISABLED_NO_CANON"


class AstrologyEngineInterface(BaseModel):
    """Placeholder interface. Calling any computation raises NotImplementedError."""

    status: AstrologyFeatureStatus = AstrologyFeatureStatus.FEATURE_DISABLED_NO_CANON

    def compute(self, *_: object, **__: object) -> None:
        raise NotImplementedError(
            "FEATURE_DISABLED_NO_CANON: astrology has no verified NUMRA canon in V1."
        )


__all__ = ["AstrologyEngineInterface", "AstrologyFeatureStatus"]
