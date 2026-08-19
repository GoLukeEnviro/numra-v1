from __future__ import annotations

from numra_numerology.mapping.pythagorean import letter_value


def build_intensity_table(calculation_string: str) -> dict[str, int]:
    """Always all nine keys "1".."9", zero-filled, with actual counts."""
    counts: dict[str, int] = {str(v): 0 for v in range(1, 10)}
    for ch in calculation_string:
        counts[str(letter_value(ch))] += 1
    return counts
