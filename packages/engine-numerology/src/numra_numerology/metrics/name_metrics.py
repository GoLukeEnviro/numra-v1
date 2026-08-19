from __future__ import annotations

from numra_numerology.mapping.pythagorean import (
    consonants_only,
    is_vowel,
    letter_value,
    map_letters,
    vowels_only,
)
from numra_numerology.metrics.karmic_debt import karmic_debt_flag
from numra_numerology.models.metric import (
    CalculationMetric,
    HiddenPassion,
    KarmicLessons,
    LetterResult,
    SubconsciousSelf,
)
from numra_numerology.models.reduction import MetricFlag
from numra_numerology.models.trace import CalculationTrace
from numra_numerology.reduction.core import reduce_compound

_NAME_INPUT_REFS = ("birth_first_names", "birth_middle_names", "birth_last_name")


def compute_expression(calculation_string: str, components: tuple[str, ...]) -> CalculationMetric:
    values = map_letters(calculation_string)
    raw = sum(values)
    reduction = reduce_compound(raw)
    trace = CalculationTrace(
        input_refs=_NAME_INPUT_REFS,
        normalization={"components": list(components), "calculation_string": calculation_string},
        operations=(
            {"type": "letter_mapping", "values": list(values)},
            {"type": "sum", "operands": list(values), "result": raw},
            {"type": "reduce", "steps": list(reduction.reduction_steps)},
        ),
    )
    flag = karmic_debt_flag("expression", raw, reduction.display_value)
    return CalculationMetric(
        metric_id="expression",
        system="pythagorean",
        method="full_name_sum_v1",
        source_value=None,
        raw_value=raw,
        root_value=reduction.root_value,
        master_number=reduction.master_number,
        effective_value=reduction.effective_value,
        display_value=reduction.display_value,
        calculation_trace=trace,
        flags=(flag,) if flag else (),
    )


def compute_soul_urge(calculation_string: str) -> CalculationMetric:
    vowels = vowels_only(calculation_string)
    flags: tuple[MetricFlag, ...] = ()

    if not vowels:
        reduction = reduce_compound(0)
        trace = CalculationTrace(
            input_refs=_NAME_INPUT_REFS,
            normalization={"calculation_string": calculation_string, "vowels_extracted": []},
            operations=({"type": "no_vowels"},),
        )
        flags = (MetricFlag(code="NO_VOWELS"),)
        raw = 0
    else:
        values = map_letters(vowels)
        raw = sum(values)
        reduction = reduce_compound(raw)
        trace = CalculationTrace(
            input_refs=_NAME_INPUT_REFS,
            normalization={
                "calculation_string": calculation_string,
                "vowels_extracted": list(vowels),
            },
            operations=(
                {"type": "letter_mapping", "values": list(values)},
                {"type": "sum", "operands": list(values), "result": raw},
                {"type": "reduce", "steps": list(reduction.reduction_steps)},
            ),
        )

    karmic = karmic_debt_flag("soul_urge", raw, reduction.display_value)
    if karmic:
        flags = flags + (karmic,)

    return CalculationMetric(
        metric_id="soul_urge",
        system="pythagorean",
        method="vowel_sum_v1",
        source_value=None,
        raw_value=reduction.raw_value,
        root_value=reduction.root_value,
        master_number=reduction.master_number,
        effective_value=reduction.effective_value,
        display_value=reduction.display_value,
        calculation_trace=trace,
        flags=flags,
    )


def compute_personality(calculation_string: str) -> CalculationMetric:
    consonants = consonants_only(calculation_string)
    values = map_letters(consonants)
    raw = sum(values)
    reduction = reduce_compound(raw)
    trace = CalculationTrace(
        input_refs=_NAME_INPUT_REFS,
        normalization={
            "calculation_string": calculation_string,
            "consonants_extracted": list(consonants),
        },
        operations=(
            {"type": "letter_mapping", "values": list(values)},
            {"type": "sum", "operands": list(values), "result": raw},
            {"type": "reduce", "steps": list(reduction.reduction_steps)},
        ),
    )
    flag = karmic_debt_flag("personality", raw, reduction.display_value)
    return CalculationMetric(
        metric_id="personality",
        system="pythagorean",
        method="consonant_sum_v1",
        source_value=None,
        raw_value=raw,
        root_value=reduction.root_value,
        master_number=reduction.master_number,
        effective_value=reduction.effective_value,
        display_value=reduction.display_value,
        calculation_trace=trace,
        flags=(flag,) if flag else (),
    )


def compute_balance(components: tuple[str, ...]) -> CalculationMetric:
    first_letters = tuple(component[0] for component in components if component)
    values = tuple(letter_value(letter) for letter in first_letters)
    raw = sum(values)
    reduction = reduce_compound(raw)
    trace = CalculationTrace(
        input_refs=("normalization.components",),
        normalization={"components": list(components), "first_letters": list(first_letters)},
        operations=(
            {"type": "letter_mapping", "values": list(values)},
            {"type": "sum", "operands": list(values), "result": raw},
            {"type": "reduce", "steps": list(reduction.reduction_steps)},
        ),
    )
    return CalculationMetric(
        metric_id="balance",
        system="pythagorean",
        method="first_letters_v1",
        source_value=None,
        raw_value=raw,
        root_value=reduction.root_value,
        master_number=reduction.master_number,
        effective_value=reduction.effective_value,
        display_value=reduction.display_value,
        calculation_trace=trace,
        flags=(),
    )


def compute_cornerstone(calculation_string: str) -> LetterResult:
    if not calculation_string:
        return LetterResult(letter=None, value=None)
    letter = calculation_string[0]
    return LetterResult(letter=letter, value=letter_value(letter))


def compute_capstone(calculation_string: str) -> LetterResult:
    if not calculation_string:
        return LetterResult(letter=None, value=None)
    letter = calculation_string[-1]
    return LetterResult(letter=letter, value=letter_value(letter))


def compute_first_vowel(calculation_string: str) -> LetterResult:
    for letter in calculation_string:
        if is_vowel(letter):
            return LetterResult(letter=letter, value=letter_value(letter))
    return LetterResult(letter=None, value=None)


def compute_hidden_passion(
    calculation_string: str, intensity_table: dict[str, int]
) -> HiddenPassion:
    max_frequency = max(intensity_table.values()) if intensity_table else 0
    values = tuple(sorted(int(k) for k, v in intensity_table.items() if v == max_frequency))
    trace = CalculationTrace(
        input_refs=("normalization.calculation_string",),
        operations=(
            {"type": "frequency_count", "intensity_table": dict(intensity_table)},
            {"type": "max_select", "max_frequency": max_frequency, "values": list(values)},
        ),
    )
    return HiddenPassion(values=values, frequency=max_frequency, calculation_trace=trace)


def compute_karmic_lessons(
    calculation_string: str, intensity_table: dict[str, int]
) -> KarmicLessons:
    missing = tuple(sorted(int(k) for k, v in intensity_table.items() if v == 0))
    trace = CalculationTrace(
        input_refs=("normalization.calculation_string",),
        operations=(
            {
                "type": "missing_values",
                "intensity_table": dict(intensity_table),
                "missing": list(missing),
            },
        ),
    )
    return KarmicLessons(values=missing, calculation_trace=trace)


def compute_subconscious_self(
    calculation_string: str, intensity_table: dict[str, int]
) -> SubconsciousSelf:
    present = tuple(sorted(int(k) for k, v in intensity_table.items() if v > 0))
    trace = CalculationTrace(
        input_refs=("normalization.calculation_string",),
        operations=(
            {
                "type": "distinct_count",
                "present_values": list(present),
                "count": len(present),
            },
        ),
    )
    return SubconsciousSelf(value=len(present), calculation_trace=trace)
