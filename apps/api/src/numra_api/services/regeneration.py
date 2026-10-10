"""D6: what a regeneration of a flagged result would do, before anyone triggers it.

A regeneration is a new, linked version created by an explicit user action -- never a batch
and never from the CLI. It goes through the same job path as a fresh generation (beta gate,
quota, persistence gate); the original stays untouched. The preview lets the user see what
the click costs: an LLM call and one unit of the feature's quota.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from enum import StrEnum

from numra_api.models.enums import BetaFeature, ContentFlag
from numra_api.services.usage_quota import QuotaSnapshot

__all__ = ["RegenerationBlock", "RegenerationPreview"]


class RegenerationBlock(StrEnum):
    #: The detector finds nothing in the original -- there is nothing to replace.
    NOT_FLAGGED = "NOT_FLAGGED"
    #: A pending or complete regeneration already exists (see ``existing_regeneration_id``).
    ALREADY_REGENERATED = "ALREADY_REGENERATED"


@dataclass(frozen=True)
class RegenerationPreview:
    content_flag: ContentFlag
    feature: BetaFeature
    existing_regeneration_id: uuid.UUID | None
    quota: QuotaSnapshot | None

    @property
    def blocked_reason(self) -> RegenerationBlock | None:
        if self.existing_regeneration_id is not None:
            return RegenerationBlock.ALREADY_REGENERATED
        if self.content_flag is ContentFlag.NONE:
            return RegenerationBlock.NOT_FLAGGED
        return None
