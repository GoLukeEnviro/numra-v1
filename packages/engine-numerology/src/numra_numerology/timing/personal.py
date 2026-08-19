from __future__ import annotations

from numra_numerology.cycles.segments import BirthSegments
from numra_numerology.models.metric import CalculationMetric
from numra_numerology.models.reduction import ReductionResult
from numra_numerology.models.trace import CalculationTrace
from numra_numerology.reduction.core import digit_sum, reduce_compound


def compute_universal_year(year: int) -> ReductionResult:
    raw = digit_sum(year)
    return reduce_compound(raw, source_value=year)


def compute_personal_year(
    segments: BirthSegments, universal_year: ReductionResult
) -> CalculationMetric:
    operands = [
        segments.month.effective_value,
        segments.day.effective_value,
        universal_year.effective_value,
    ]
    raw = sum(operands)
    reduction = reduce_compound(raw)
    trace = CalculationTrace(
        input_refs=("birth_date", "as_of_date"),
        operations=(
            {"type": "sum", "operands": operands, "result": raw},
            {"type": "reduce", "steps": list(reduction.reduction_steps)},
        ),
    )
    return CalculationMetric(
        metric_id="personal_year",
        system="numra-canonical",
        method="segmented_v1",
        source_value=universal_year.source_value,
        raw_value=raw,
        root_value=reduction.root_value,
        master_number=reduction.master_number,
        effective_value=reduction.effective_value,
        display_value=reduction.display_value,
        calculation_trace=trace,
        flags=(),
    )


def compute_personal_month(
    personal_year: CalculationMetric, calendar_month: int
) -> CalculationMetric:
    calendar_month_reduction = reduce_compound(calendar_month)
    operands = [personal_year.effective_value, calendar_month_reduction.effective_value]
    raw = sum(operands)
    reduction = reduce_compound(raw)
    trace = CalculationTrace(
        input_refs=("personal_year", "as_of_date"),
        operations=(
            {"type": "sum", "operands": operands, "result": raw},
            {"type": "reduce", "steps": list(reduction.reduction_steps)},
        ),
    )
    return CalculationMetric(
        metric_id="personal_month",
        system="numra-canonical",
        method="segmented_v1",
        source_value=calendar_month,
        raw_value=raw,
        root_value=reduction.root_value,
        master_number=reduction.master_number,
        effective_value=reduction.effective_value,
        display_value=reduction.display_value,
        calculation_trace=trace,
        flags=(),
    )


def compute_personal_day(personal_month: CalculationMetric, calendar_day: int) -> CalculationMetric:
    calendar_day_reduction = reduce_compound(calendar_day)
    operands = [personal_month.effective_value, calendar_day_reduction.effective_value]
    raw = sum(operands)
    reduction = reduce_compound(raw)
    trace = CalculationTrace(
        input_refs=("personal_month", "as_of_date"),
        operations=(
            {"type": "sum", "operands": operands, "result": raw},
            {"type": "reduce", "steps": list(reduction.reduction_steps)},
        ),
    )
    return CalculationMetric(
        metric_id="personal_day",
        system="numra-canonical",
        method="segmented_v1",
        source_value=calendar_day,
        raw_value=raw,
        root_value=reduction.root_value,
        master_number=reduction.master_number,
        effective_value=reduction.effective_value,
        display_value=reduction.display_value,
        calculation_trace=trace,
        flags=(),
    )
