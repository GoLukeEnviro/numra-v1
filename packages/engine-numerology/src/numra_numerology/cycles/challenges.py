from __future__ import annotations

from numra_numerology.cycles.segments import BirthSegments
from numra_numerology.models.cycles import Challenges


def compute_challenges(segments: BirthSegments) -> Challenges:
    """canon-spec.md §25. Root values only, no Master Number classification. 0 is valid."""
    month, day, year = segments.month.root_value, segments.day.root_value, segments.year.root_value
    c1 = abs(day - month)
    c2 = abs(day - year)
    c3 = abs(c1 - c2)
    c4 = abs(month - year)
    return Challenges(challenge_1=c1, challenge_2=c2, challenge_3=c3, challenge_4=c4)
