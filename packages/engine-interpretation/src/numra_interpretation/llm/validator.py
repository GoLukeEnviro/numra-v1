"""The per-claim Report Numerical Linter.

Given generated text/structured output that may contain ``{{metric:ID}}``/
``{{special:ID}}``-style placeholders and/or explicit `NumericClaim`s, this verifies
every claim's ``display_value`` exactly matches the `CanonicalProfile` it is supposed
to describe, and that every placeholder references a known id. Any mismatch raises
`InvalidReportSection` — there is no silent correction, no "closest match", no
rounding.

Two placeholder namespaces:

- ``{{metric:ID}}`` — a single scalar fact with one ``display_value`` string (life
  path, pinnacles, challenges, cornerstone/capstone/first_vowel, universal_year, ...).
- ``{{special:ID}}`` — a fact that is not a single scalar (hidden passion's values +
  frequency, karmic lessons' list) and needs its own deterministic textual rendering,
  built once here (`format_hidden_passion`/`format_karmic_lessons`) so the same
  rendering is used for both claim validation and placeholder resolution
  (`report/pipeline.py`) — never re-derived ad hoc at each call site.

Scope: this validates *individual* claims/placeholders against the profile's
`core_numbers`, `cycles`, and `timing` sections. A fuller multi-section report linter
(cross-section consistency, narrative-level checks) lives in `report/linter.py`.
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
]

_PLACEHOLDER_PATTERN = re.compile(r"\{\{\s*metric\s*:\s*([a-zA-Z0-9_]+)\s*\}\}")
_SPECIAL_PLACEHOLDER_PATTERN = re.compile(r"\{\{\s*special\s*:\s*([a-zA-Z0-9_]+)\s*\}\}")
_ANY_PLACEHOLDER_PATTERN = re.compile(r"\{\{\s*(?:metric|special)\s*:\s*[a-zA-Z0-9_]+\s*\}\}")

#: `core_numbers` fields that are `CalculationMetric` instances with a `metric_id` +
#: `display_value`.
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

#: `core_numbers` fields carrying a single letter+value (cornerstone/capstone/first
#: vowel) — reduced to a display string here (the letter, uppercased) since a report
#: cites the letter, not the raw numeric value, for these.
_LETTER_METRIC_IDS: tuple[str, ...] = ("cornerstone", "capstone", "first_vowel")

#: `timing` fields that carry a `display_value` directly comparable to a claim.
_TIMING_METRIC_IDS: tuple[str, ...] = ("personal_year", "personal_month", "personal_day")


def build_metric_display_value_index(profile: CanonicalProfile) -> dict[str, str]:
    """Build a ``metric_id -> display_value`` lookup covering every scalar fact in a
    `CanonicalProfile` — the ground truth for ``{{metric:ID}}`` claim validation."""
    index: dict[str, str] = {}
    for metric_id in _CORE_METRIC_IDS:
        index[metric_id] = getattr(profile.core_numbers, metric_id).display_value
    for metric_id in _LETTER_METRIC_IDS:
        letter_result = getattr(profile.core_numbers, metric_id)
        index[metric_id] = letter_result.letter.upper() if letter_result.letter else "—"
    for metric_id in _TIMING_METRIC_IDS:
        index[metric_id] = getattr(profile.timing, metric_id).display_value
    # universal_year is a bare ReductionResult (no metric_id of its own on the model),
    # but it is a legitimate, known timing fact a report may cite.
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
    """The single canonical textual rendering of Hidden Passion — used identically for
    claim validation and for resolving ``{{special:hidden_passion}}``."""
    hidden_passion = profile.core_numbers.hidden_passion
    values = ", ".join(str(value) for value in hidden_passion.values)
    return f"{values} (Häufigkeit {hidden_passion.frequency})"


def format_karmic_lessons(profile: CanonicalProfile) -> str:
    """The single canonical textual rendering of Karmic Lessons — used identically for
    claim validation and for resolving ``{{special:karmic_lessons}}``."""
    karmic_lessons = profile.core_numbers.karmic_lessons
    if not karmic_lessons.values:
        return "keine"
    return ", ".join(str(value) for value in karmic_lessons.values)


def build_special_claim_index(profile: CanonicalProfile) -> dict[str, str]:
    """Build the ``special_id -> rendered text`` lookup for the non-scalar facts that
    use the ``{{special:ID}}`` placeholder namespace instead of ``{{metric:ID}}``."""
    return {
        "hidden_passion": format_hidden_passion(profile),
        "karmic_lessons": format_karmic_lessons(profile),
    }


def extract_placeholder_metric_ids(text: str) -> tuple[str, ...]:
    """Extract every ``{{metric:ID}}`` placeholder's ``ID`` from free text, in order of
    first appearance, deduplicated."""
    seen: dict[str, None] = {}
    for match in _PLACEHOLDER_PATTERN.finditer(text):
        seen.setdefault(match.group(1), None)
    return tuple(seen)


def extract_special_placeholder_ids(text: str) -> tuple[str, ...]:
    """Extract every ``{{special:ID}}`` placeholder's ``ID`` from free text, in order
    of first appearance, deduplicated."""
    seen: dict[str, None] = {}
    for match in _SPECIAL_PLACEHOLDER_PATTERN.finditer(text):
        seen.setdefault(match.group(1), None)
    return tuple(seen)


def find_unauthorized_numeric_literals(text: str, profile: CanonicalProfile) -> tuple[str, ...]:
    """Find bare (non-placeholder) multi-digit tokens in ``text`` that coincide with one
    of this profile's own canonical numerology values — evidence the generator typed a
    numerology fact as a literal digit instead of citing it via ``{{metric:ID}}``/
    ``{{special:ID}}``, which is forbidden regardless of whether the digit happens to be
    correct (a correct-but-unauthorized literal is still not traceable/auditable the
    way a resolved placeholder is).

    Scoped to runs of 2+ digits deliberately: single digits 1-9 are common in ordinary
    prose (list items, "Schritt 3", etc.) and would make this check impractically
    noisy; every distinctive numerology value this system cites (master numbers,
    two-digit raw/root values, pinnacle/challenge values) is 2+ digits or contains a
    2+-digit component (e.g. a "22/4"-style display value)."""
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
    """Self-heal each claim's ``display_value`` against the profile instead of
    rejecting the whole section over it — the primary entry point a generation
    pipeline should call on a provider's raw `numeric_claims` output.

    User-approved fix for a production regression (V1.6 D-2): even after the model
    reliably names the *correct* ``metric_id`` for every required claim (fixing the
    two prior failure modes — missing claims, and placeholder-syntax-as-value), it
    still occasionally types the wrong literal digit into ``display_value`` — e.g.
    claiming ``birthday`` is ``'4'`` when the canonical value is ``'18/9'``. This is
    inherent sampling variance at the provider's temperature 0.2 (see
    `_DEFAULT_TEMPERATURE` in `ollama_provider.py`), not a further prompt-wording
    gap: across a report's many sections and claims, even a small per-claim
    non-compliance rate compounds into frequent validation failures.

    The pipeline (`build_metric_display_value_index`/`build_special_claim_index`) is
    the sole authoritative source for every numeric fact a report can cite — the
    model was already given each canonical value verbatim in the prompt. There is
    therefore no correctness or security reason to trust, or even require, the model
    to retype that value exactly: only *which* ``metric_id`` a claim is about is
    actually meaningful signal contributed by the model, and only that continues to
    be enforced strictly here.

    A claim whose ``metric_id`` is not found in either index still raises
    `InvalidReportSection` exactly as `validate_numeric_claims` does — an invented id
    indicates real confusion about which facts exist, not just a mistyped value, and
    that failure mode is not self-healable."""
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
    """Raise `InvalidReportSection` if any claim references an unknown id (checked
    across both the scalar metric index and the special/non-scalar index) or a
    ``display_value`` that does not exactly match the profile.

    Kept as a strict assertion helper (still used by `validate_generation_result` and
    by tests that want a hard failure on any mismatch) alongside the newer
    `normalize_numeric_claims`, which is what the report generation pipeline actually
    calls — see its docstring for why a mismatched-but-known claim is self-healed
    there rather than rejected."""
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
    """Raise `InvalidReportSection` if a section's own declared metric refs (e.g. a
    `timing` section's personal_year/month/day) are not all cited by its returned
    `claims`. Coverage is exact-id membership, so a claim about a different metric
    (e.g. `pinnacle_1`) can never satisfy coverage of an id it isn't.

    Added for the V1.6 C timing-report production bug: a real provider, given weak
    timing-specific grounding, recycled the previous section's Pinnacles/Challenges
    content (or claimed personal_year/month/day were unavailable) instead of citing
    the declared facts — nothing previously checked that a section's generated
    `numeric_claims` actually covered what its own manifest spec required."""
    cited = {claim.metric_id for claim in claims}
    missing = [metric_id for metric_id in required_metric_ids if metric_id not in cited]
    if missing:
        raise InvalidReportSection(
            f"MissingMetricCoverage: section {section_id!r} must cite "
            f"{list(required_metric_ids)} but its numeric_claims is missing {missing!r}"
        )


def validate_generation_result(
    text: str, claims: tuple[NumericClaim, ...], profile: CanonicalProfile
) -> None:
    """Full per-claim validation: checks `claims` against the profile (see
    `validate_numeric_claims`) and additionally checks every ``{{metric:ID}}``/
    ``{{special:ID}}`` placeholder found in ``text`` references a known id."""
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
