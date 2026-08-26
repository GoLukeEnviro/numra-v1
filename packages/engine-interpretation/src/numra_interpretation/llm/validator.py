"""The per-claim Report Numerical Linter.

Given generated text/structured output that may contain ``{{metric:ID}}``/
``{{special:ID}}``-style placeholders and/or explicit `NumericClaim`s, this verifies
every claim's ``display_value`` exactly matches the `CanonicalProfile` it is supposed
to describe, and that every placeholder references a known id. Any mismatch raises
`InvalidReportSection` — there is no silent correction, no "closest match", no
rounding.
"""

from __future__ import annotations

import re

from numra_interpretation.errors import InvalidReportSection
from numra_interpretation.llm.types import NumericClaim
from numra_numerology.models.profile import CanonicalProfile

__all__ = [
    "build_metric_display_value_index",
    "build_special_claim_index",
    "extract_placeholder_metric_ids",
    "extract_special_placeholder_ids",
    "find_unauthorized_numeric_literals",
    "format_hidden_passion",
    "format_karmic_lessons",
    "normalize_numeric_claims",
    "validate_generation_result",
    "validate_metric_ref_coverage",
    "validate_numeric_claims",
    "validate_placeholder_coverage",
]

_PLACEHOLDER_PATTERN = re.compile(r"\{\{\s*metric\s*:\s*([a-zA-Z0-9_]+)\s*\}\}")
_SPECIAL_PLACEHOLDER_PATTERN = re.compile(r"\{\{\s*special\s*:\s*([a-zA-Z0-9_]+)\s*\}\}")
_ANY_PLACEHOLDER_PATTERN = re.compile(r"\{\{\s*(?:metric|special)\s*:\s*[a-zA-Z0-9_]+\s*\}\}")

_CORE_METRIC_IDS: tuple[str, ...] = (
    "life_path",
    "birthday",
    "attitude",
    "expression",
    "soul_urge",
    "personality",
    "maturity",
    "balance",
)
_LETTER_METRIC_IDS: tuple[str, ...] = ("cornerstone", "capstone", "first_vowel")
_TIMING_METRIC_IDS: tuple[str, ...] = ("personal_year", "personal_month", "personal_day")


def build_metric_display_value_index(profile: CanonicalProfile) -> dict[str, str]:
    index: dict[str, str] = {}
    for metric_id in _CORE_METRIC_IDS:
        index[metric_id] = getattr(profile.core_numbers, metric_id).display_value
    for metric_id in _LETTER_METRIC_IDS:
        letter_result = getattr(profile.core_numbers, metric_id)
        index[metric_id] = letter_result.letter.upper() if letter_result.letter else "—"
    for metric_id in _TIMING_METRIC_IDS:
        index[metric_id] = getattr(profile.timing, metric_id).display_value
    index["universal_year"] = profile.timing.universal_year.display_value

    pinnacles = profile.cycles.pinnacles
    index["pinnacle_1"] = pinnacles.pinnacle_1.display_value
    index["pinnacle_2"] = pinnacles.pinnacle_2.display_value
    index["pinnacle_3"] = pinnacles.pinnacle_3.display_value
    index["pinnacle_4"] = pinnacles.pinnacle_4.display_value

    challenges = profile.cycles.challenges
    index["challenge_1"] = str(challenges.challenge_1)
    index["challenge_2"] = str(challenges.challenge_2)
    index["challenge_3"] = str(challenges.challenge_3)
    index["challenge_4"] = str(challenges.challenge_4)

    index["subconscious_self"] = str(profile.core_numbers.subconscious_self.value)
    return index


def format_hidden_passion(profile: CanonicalProfile) -> str:
    hidden_passion = profile.core_numbers.hidden_passion
    values = ", ".join(str(value) for value in hidden_passion.values)
    return f"{values} (Häufigkeit {hidden_passion.frequency})"


def format_karmic_lessons(profile: CanonicalProfile) -> str:
    karmic_lessons = profile.core_numbers.karmic_lessons
    if not karmic_lessons.values:
        return "keine"
    return ", ".join(str(value) for value in karmic_lessons.values)


def build_special_claim_index(profile: CanonicalProfile) -> dict[str, str]:
    return {
        "hidden_passion": format_hidden_passion(profile),
        "karmic_lessons": format_karmic_lessons(profile),
    }


def extract_placeholder_metric_ids(text: str) -> tuple[str, ...]:
    seen: dict[str, None] = {}
    for match in _PLACEHOLDER_PATTERN.finditer(text):
        seen.setdefault(match.group(1), None)
    return tuple(seen)


def extract_special_placeholder_ids(text: str) -> tuple[str, ...]:
    seen: dict[str, None] = {}
    for match in _SPECIAL_PLACEHOLDER_PATTERN.finditer(text):
        seen.setdefault(match.group(1), None)
    return tuple(seen)


def find_unauthorized_numeric_literals(text: str, profile: CanonicalProfile) -> tuple[str, ...]:
    stripped = _ANY_PLACEHOLDER_PATTERN.sub(" ", text)

    forbidden: set[str] = set()
    all_values = list(build_metric_display_value_index(profile).values())
    all_values += list(build_special_claim_index(profile).values())
    for value in all_values:
        for digits in re.findall(r"\d+", value):
            if len(digits) >= 2:
                forbidden.add(digits)

    found: list[str] = []
    seen: set[str] = set()
    for match in re.finditer(r"(?<!\d)\d{2,}(?!\d)", stripped):
        token = match.group(0)
        if token in forbidden and token not in seen:
            seen.add(token)
            found.append(token)
    return tuple(found)


def normalize_numeric_claims(
    claims: tuple[NumericClaim, ...], profile: CanonicalProfile
) -> tuple[NumericClaim, ...]:
    index = build_metric_display_value_index(profile)
    special_index = build_special_claim_index(profile)
    normalized: list[NumericClaim] = []
    for claim in claims:
        if claim.metric_id in index:
            actual = index[claim.metric_id]
        elif claim.metric_id in special_index:
            actual = special_index[claim.metric_id]
        else:
            raise InvalidReportSection(f"Unknown metric_id in numeric claim: {claim.metric_id!r}")
        if claim.display_value != actual:
            normalized.append(claim.model_copy(update={"display_value": actual}))
        else:
            normalized.append(claim)
    return tuple(normalized)


def validate_numeric_claims(claims: tuple[NumericClaim, ...], profile: CanonicalProfile) -> None:
    index = build_metric_display_value_index(profile)
    special_index = build_special_claim_index(profile)
    for claim in claims:
        if claim.metric_id in index:
            actual = index[claim.metric_id]
        elif claim.metric_id in special_index:
            actual = special_index[claim.metric_id]
        else:
            raise InvalidReportSection(f"Unknown metric_id in numeric claim: {claim.metric_id!r}")
        if claim.display_value != actual:
            raise InvalidReportSection(
                f"Numeric claim mismatch for metric_id={claim.metric_id!r}: "
                f"claimed display_value={claim.display_value!r}, "
                f"canonical display_value={actual!r}"
            )


def validate_metric_ref_coverage(
    claims: tuple[NumericClaim, ...], required_metric_ids: tuple[str, ...], *, section_id: str
) -> None:
    cited = {claim.metric_id for claim in claims}
    missing = [metric_id for metric_id in required_metric_ids if metric_id not in cited]
    if missing:
        raise InvalidReportSection(
            f"MissingMetricCoverage: section {section_id!r} must cite "
            f"{list(required_metric_ids)} but its numeric_claims is missing {missing!r}"
        )


def validate_placeholder_coverage(
    text: str, required_metric_ids: tuple[str, ...], *, section_id: str
) -> None:
    """Coverage from placeholders in `text`, not from model-emitted numeric_claims."""
    cited = set(extract_placeholder_metric_ids(text)) | set(extract_special_placeholder_ids(text))
    missing = [metric_id for metric_id in required_metric_ids if metric_id not in cited]
    if missing:
        raise InvalidReportSection(
            f"MissingMetricCoverage: section {section_id!r} must cite "
            f"{list(required_metric_ids)} via placeholders but text is missing {missing!r}"
        )


def validate_generation_result(
    text: str, claims: tuple[NumericClaim, ...], profile: CanonicalProfile
) -> None:
    index = build_metric_display_value_index(profile)
    special_index = build_special_claim_index(profile)
    for metric_id in extract_placeholder_metric_ids(text):
        if metric_id not in index:
            raise InvalidReportSection(
                f"Unknown metric_id referenced by placeholder: {{{{metric:{metric_id}}}}}"
            )
    for special_id in extract_special_placeholder_ids(text):
        if special_id not in special_index:
            raise InvalidReportSection(
                f"Unknown special id referenced by placeholder: {{{{special:{special_id}}}}}"
            )
    validate_numeric_claims(claims, profile)
