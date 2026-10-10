from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel

from numra_api.models.enums import BetaFeature, ContentFlag
from numra_api.services.regeneration import RegenerationBlock

if TYPE_CHECKING:
    from numra_api.services.regeneration import RegenerationPreview


class QuotaPreviewOut(BaseModel):
    """The caller's current usage of the feature a start consumes."""

    window_limit: int | None
    window_seconds: int
    used_in_window: int
    concurrent_limit: int | None
    active: int
    would_exceed: bool


class RegenerationPreviewOut(BaseModel):
    """What "regenerate" would do. Nothing is started by reading it."""

    content_flag: ContentFlag
    can_regenerate: bool
    blocked_reason: RegenerationBlock | None
    existing_regeneration_id: str | None
    #: A regeneration calls the language model, like a fresh generation.
    uses_llm: bool = True
    #: The feature whose limit one regeneration consumes (one unit).
    feature: BetaFeature
    units: int = 1
    #: The original is kept as it is; the result is a new, linked version.
    original_kept: bool = True
    quota: QuotaPreviewOut | None

    @classmethod
    def from_preview(cls, preview: RegenerationPreview) -> RegenerationPreviewOut:
        quota = preview.quota
        blocked = preview.blocked_reason
        return cls(
            content_flag=preview.content_flag,
            can_regenerate=blocked is None,
            blocked_reason=blocked,
            existing_regeneration_id=(
                None
                if preview.existing_regeneration_id is None
                else str(preview.existing_regeneration_id)
            ),
            feature=preview.feature,
            quota=(
                None
                if quota is None
                else QuotaPreviewOut(
                    window_limit=quota.limits.max_per_window,
                    window_seconds=quota.limits.window_seconds,
                    used_in_window=quota.used_in_window,
                    concurrent_limit=quota.limits.max_concurrent,
                    active=quota.active,
                    would_exceed=quota.would_exceed,
                )
            ),
        )
