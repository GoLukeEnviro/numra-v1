from __future__ import annotations

from numra_numerology.models.reduction import MASTER_NUMBERS, ReductionResult


def digit_sum(n: int) -> int:
    return sum(int(d) for d in str(n))


def compute_display_value(raw_value: int, root_value: int, master_number: int | None) -> str:
    """Verbatim display rule — canon-spec.md §2. MUST NOT be reinterpreted."""
    if master_number is not None:
        return f"{master_number}/{root_value}"
    if raw_value > 9:
        return f"{raw_value}/{root_value}"
    return str(raw_value)


def reduce_compound(raw_value: int, *, source_value: int | str | None = None) -> ReductionResult:
    """Reduce a non-negative composite integer, preserving Master Numbers {11,22,33} the
    instant they are reached in the reduction path. Integer arithmetic only."""
    if raw_value < 0:
        raise ValueError("raw_value must be >= 0")

    if raw_value == 0:
        return ReductionResult(
            source_value=source_value,
            raw_value=0,
            root_value=0,
            master_number=None,
            effective_value=0,
            display_value="0",
            reduction_steps=(0,),
        )

    current = raw_value
    steps: list[int] = [current]

    while current >= 10:
        if current in MASTER_NUMBERS:
            break
        current = digit_sum(current)
        steps.append(current)

    if current in MASTER_NUMBERS:
        master: int | None = current
        root = current
        while root >= 10:
            root = digit_sum(root)
        effective = current
    else:
        master = None
        root = current
        effective = current

    return ReductionResult(
        source_value=source_value,
        raw_value=raw_value,
        root_value=root,
        master_number=master,
        effective_value=effective,
        display_value=compute_display_value(raw_value, root, master),
        reduction_steps=tuple(steps),
    )
