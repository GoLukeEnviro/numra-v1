from __future__ import annotations

import datetime as dt

from numra_numerology.cycles.segments import BirthSegments
from numra_numerology.metrics.karmic_debt import karmic_debt_flag
from numra_numerology.models.metric import CalculationMetric
from numra_numerology.models.trace import CalculationTrace
from numra_numerology.reduction.core import digit_sum, reduce_compound


def compute_life_path(segments: BirthSegments) -> CalculationMetric:
    operands = [
        segments.day.effective_value,
        segments.month.effective_value,
        segments.year.effective_value,
    ]
    raw = sum(operands)
    reduction = reduce_compound(raw)
    trace = CalculationTrace(
        input_refs=("birth_date",),
        normalization={
            "day_segment": segments.day.source_value,
            "month_segment": segments.month.source_value,
            "year_segment": segments.year.source_value,
        },
        operations=(
            {
                "type": "segment_reduce",
                "segment": "day",
                "source_value": segments.day.source_value,
                "raw_value": segments.day.raw_value,
                "steps": list(segments.day.reduction_steps),
                "effective": segments.day.effective_value,
            },
            {
                "type": "segment_reduce",
                "segment": "month",
                "source_value": segments.month.source_value,
                "raw_value": segments.month.raw_value,
                "steps": list(segments.month.reduction_steps),
                "effective": segments.month.effective_value,
            },
            {
                "type": "segment_reduce",
                "segment": "year",
                "source_value": segments.year.source_value,
                "raw_value": segments.year.raw_value,
                "steps": list(segments.year.reduction_steps),
                "effective": segments.year.effective_value,
            },
            {"type": "sum", "operands": list(operands), "result": raw},
            {"type": "reduce", "steps": list(reduction.reduction_steps)},
        ),
    )
    flag = karmic_debt_flag("life_path", raw, reduction.display_value)
    return CalculationMetric(
        metric_id="life_path",
        system="numra-canonical",
        method="segmented_v1",
        source_value=None,
        raw_value=raw,
        root_value=reduction.root_value,
        master_number=reduction.master_number,
        effective_value=reduction.effective_value,
        display_value=reduction.display_value,
        calculation_trace=trace,
        flags=(flag,) if flag else (),
    )


def compute_life_path_direct_diagnostic(birth_date: dt.date) -> CalculationMetric:
    """Non-canonical diagnostic — never a second Life Path. canon-spec.md §9."""
    digits_str = f"{birth_date.day:02d}{birth_date.month:02d}{birth_date.year:04d}"
    operands = [int(d) for d in digits_str]
    raw = sum(operands)
    reduction = reduce_compound(raw)
    trace = CalculationTrace(
        input_refs=("birth_date",),
        operations=(
            {"type": "digit_concat", "digits_string": digits_str},
            {"type": "sum", "operands": operands, "result": raw},
            {"type": "reduce", "steps": list(reduction.reduction_steps)},
        ),
    )
    return CalculationMetric(
        metric_id="life_path_direct_diagnostic",
        system="numra-canonical",
        method="direct_digit_sum",
        source_value=digits_str,
        raw_value=raw,
        root_value=reduction.root_value,
        master_number=reduction.master_number,
        effective_value=reduction.effective_value,
        display_value=reduction.display_value,
        calculation_trace=trace,
        flags=(),
    )


def compute_birthday(birth_date: dt.date) -> CalculationMetric:
    reduction = reduce_compound(birth_date.day, source_value=birth_date.day)
    trace = CalculationTrace(
        input_refs=("birth_date",),
        operations=(
            {"type": "reduce", "operand": birth_date.day, "steps": list(reduction.reduction_steps)},
        ),
    )
    flag = karmic_debt_flag("birthday", reduction.raw_value, reduction.display_value)
    return CalculationMetric(
        metric_id="birthday",
        system="numra-canonical",
        method="segmented_v1",
        source_value=birth_date.day,
        raw_value=reduction.raw_value,
        root_value=reduction.root_value,
        master_number=reduction.master_number,
        effective_value=reduction.effective_value,
        display_value=reduction.display_value,
        calculation_trace=trace,
        flags=(flag,) if flag else (),
    )


def compute_attitude(birth_date: dt.date) -> CalculationMetric:
    raw = birth_date.month + birth_date.day
    reduction = reduce_compound(raw)
    trace = CalculationTrace(
        input_refs=("birth_date",),
        operations=(
            {"type": "sum", "operands": [birth_date.month, birth_date.day], "result": raw},
            {"type": "reduce", "steps": list(reduction.reduction_steps)},
        ),
    )
    return CalculationMetric(
        metric_id="attitude",
        system="numra-canonical",
        method="segmented_v1",
        source_value=None,
        raw_value=raw,
        root_value=reduction.root_value,
        master_number=reduction.master_number,
        effective_value=reduction.effective_value,
        display_value=reduction.display_value,
        calculation_trace=trace,
        flags=(),
    )


def compute_maturity(life_path_root: int, expression_root: int) -> CalculationMetric:
    raw = life_path_root + expression_root
    reduction = reduce_compound(raw)
    trace = CalculationTrace(
        input_refs=("life_path", "expression"),
        operations=(
            {"type": "sum", "operands": [life_path_root, expression_root], "result": raw},
            {"type": "reduce", "steps": list(reduction.reduction_steps)},
        ),
    )
    return CalculationMetric(
        metric_id="maturity",
        system="numra-canonical",
        method="root_sum_v1",
        source_value=None,
        raw_value=raw,
        root_value=reduction.root_value,
        master_number=reduction.master_number,
        effective_value=reduction.effective_value,
        display_value=reduction.display_value,
        calculation_trace=trace,
        flags=(),
    )


__all__ = [
    "compute_attitude",
    "compute_birthday",
    "compute_life_path",
    "compute_life_path_direct_diagnostic",
    "compute_maturity",
    "digit_sum",
]
