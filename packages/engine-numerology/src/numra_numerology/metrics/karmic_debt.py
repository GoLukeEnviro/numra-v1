from __future__ import annotations

from numra_numerology.models.reduction import MetricFlag

#: Recognized Karmic Debt compounds — canon-spec.md §21. Exact raw_value match only.
KARMIC_DEBT_VALUES: frozenset[int] = frozenset({13, 14, 16, 19})

#: Metrics eligible for automatic Karmic Debt flagging — canon-spec.md §21.
KARMIC_DEBT_ALLOWLIST: frozenset[str] = frozenset(
    {"life_path", "birthday", "expression", "soul_urge", "personality"}
)


def karmic_debt_flag(metric_id: str, raw_value: int, display_value: str) -> MetricFlag | None:
    if metric_id not in KARMIC_DEBT_ALLOWLIST:
        return None
    if raw_value not in KARMIC_DEBT_VALUES:
        return None
    return MetricFlag(code="KARMIC_DEBT", value=display_value, source_raw_value=raw_value)
