# NUMRA Canon Specification — v1.0.0

Status: **FROZEN** unless a section is explicitly marked `RESERVED_UNFROZEN` or
`FEATURE_DISABLED_NO_CANON`. Frozen rules MUST be implemented exactly as written here.
Unfrozen rules MUST NOT be implemented with an invented formula — only an interface/flag.

```
calculation_system = "numra-canonical"
calculation_version = "1.0.0"
schema_version = "1.0.0"
knowledge_system = "numra"
knowledge_version = "1.0.0"
language = "de"
```

Mapping system: `pythagorean` only. No Chaldean/Kabbalistic values may be mixed into this
canon. Vowels: `A E I O U` only — `Y` is always a consonant, no contextual exception in V1.

---

## 0. Determinism Contract

- The engine is pure: no DB, no HTTP, no LLM import, no filesystem I/O, no global mutable
  state, no `random`, no `datetime.now()` / `date.today()`.
- All time-dependent calculations (Universal/Personal Year/Month/Day, Pinnacle/Challenge age
  windows) take an explicit `as_of_date: date` parameter.
- Integer arithmetic only. No floats anywhere in the reduction or metric pipeline.
- Same input + same `MethodPolicy` ⇒ byte-identical `CanonicalProfile` JSON
  (`sort_keys=True` serialization) and identical `deterministic_hash` (SHA-256 over a
  `CalculationHashEnvelope`: schema version, calculation version, normalized inputs, policy,
  results, trace).

---

## 1. Master Numbers

Only `11`, `22`, `33` are Master Numbers in V1.

`44`, `55`, `66`, `77`, `88`, `99` are **not** Master Numbers — they reduce further
(`44 → 8`, display `"44/8"`, `master_number = null`).

---

## 2. Reduction Algorithm (`reduce_compound`)

**Definition.** Converts a non-negative composite integer into a `ReductionResult` while
preserving Master Numbers `{11, 22, 33}` the moment they are reached in the reduction path,
and recording every intermediate digit-sum step for traceability.

**Input.** `raw_value: int >= 0`.

**Algorithm** (integer arithmetic only):

```text
MASTER_NUMBERS = {11, 22, 33}

def digit_sum(n: int) -> int:
    return sum(int(d) for d in str(n))

def reduce_compound(raw_value: int) -> ReductionResult:
    if raw_value < 0:
        raise ValueError("raw_value must be >= 0")

    if raw_value == 0:
        return ReductionResult(
            source_value=None, raw_value=0, root_value=0,
            master_number=None, effective_value=0,
            display_value="0", reduction_steps=[0],
        )

    current = raw_value
    steps = [current]

    while current >= 10:
        if current in MASTER_NUMBERS:
            break
        current = digit_sum(current)
        steps.append(current)

    if current in MASTER_NUMBERS:
        master = current
        # root is the single-digit root of the master number itself
        root = current
        while root >= 10:
            root = digit_sum(root)
        effective = current
    else:
        master = None
        root = current
        effective = current

    return ReductionResult(
        source_value=None, raw_value=raw_value, root_value=root,
        master_number=master, effective_value=effective,
        display_value=compute_display_value(raw_value, root, master),
        reduction_steps=steps,
    )
```

**Reduction Boundary.** Reduction stops the instant the running value is `11`, `22`, or `33`
— even if that value was reached directly from the first digit-sum pass. It never reduces a
master number down to its single root as the *effective* value; only `root_value` reflects
the single-digit root of a master number.

**Master Rule.** If the reduction path ever equals `11`, `22`, or `33`, `effective_value`
becomes that master number and `master_number` is set. Numbers that are merely *compounds
containing* those digits (e.g. `211`) are not special-cased — only an exact intermediate
value of `11`/`22`/`33` triggers preservation.

**Display Rule** (verbatim, MUST NOT be reinterpreted):

```python
if master_number is not None:
    display_value = f"{master_number}/{root_value}"
elif raw_value > 9:
    display_value = f"{raw_value}/{root_value}"
else:
    display_value = str(raw_value)
```

Note: when a master number is reached via an intermediate step (e.g. `29 → 11 → 2`), the
display uses the **master number reached**, not the original `raw_value`:
`29 → display_value = "11/2"`, not `"29/2"`. `raw_value=29` and
`reduction_steps=[29, 11]` remain fully traceable.

**Test Requirements.** See §Reduction Test Matrix below — all pairs MUST be covered by unit
tests, plus Hypothesis property tests for termination, root range `[0,9]`, master range
`{null,11,22,33}`, and "no false master" for 44/55/66/77/88/99.

### Reduction Test Matrix

| raw_value | display_value |
|---|---|
| 0 | `0` |
| 1 | `1` |
| 9 | `9` |
| 10 | `10/1` |
| 11 | `11/2` |
| 12 | `12/3` |
| 13 | `13/4` |
| 19 | `19/1` |
| 22 | `22/4` |
| 29 | `11/2` |
| 33 | `33/6` |
| 38 | `11/2` |
| 44 | `44/8` |
| 55 | `55/1` |
| 99 | `99/9` |

---

## 3. Name Normalization Pipeline

**Order (verbatim):**

```
RAW INPUT
→ Unicode NFC
→ Trim
→ Uppercase
→ explicit German replacements
→ Unicode decomposition (NFD) + combining-diacritic stripping
→ tokenize into components
→ A–Z validation
→ build calculation_string (components joined, no separators)
```

**Explicit German replacements (before generic decomposition):**

| Input | Output |
|---|---|
| `Ä`/`ä` | `A` |
| `Ö`/`ö` | `O` |
| `Ü`/`ü` | `U` |
| `ß`/`ẞ` | `SS` |

These are **not** `AE`/`OE`/`UE` expansions — that would be a MAJOR version change.

**Generic Latin diacritics** (post decomposition, combining marks stripped): `É È Ê → E`,
`Á À → A`, `Ñ → N`, `Ç → C`, and any other Latin letter with a combining diacritic reduces to
its base Latin letter via NFD decomposition + combining-mark removal.

**Tokenization separators:** whitespace, `-` (hyphen-minus), `‐` (U+2010 hyphen), `-`
(U+2011 non-breaking hyphen), `–` (en dash), `—` (em dash), `'` (apostrophe), `’` (U+2019
right single quote). Empty components after tokenization are discarded. Other typographic
punctuation is stripped prior to component formation. Digits are never a valid name
component character.

**Unsupported scripts.** If, after the full pipeline, any character remains outside `A–Z`,
normalization fails with error code `NORMALIZATION_UNSUPPORTED_SCRIPT`. No automatic
transliteration of Cyrillic, CJK, Arabic, Greek, or other non-Latin scripts is performed by
this engine or any dependency.

**Structured output:**

```json
{
  "original": "Lukas Springer",
  "components": ["LUKAS", "SPRINGER"],
  "calculation_string": "LUKASSPRINGER"
}
```

`calculation_string` (concatenation, no separators) is the basis for Expression, Soul Urge,
Personality, Hidden Passion, Karmic Lessons, Subconscious Self, Cornerstone, Capstone, First
Vowel, and the Intensity Table. `components` (per-token, first-letter access) is the basis
for Balance Number and Identity Timeline/debugging.

---

## 4. Pythagorean Letter Mapping

```
1 = A J S      2 = B K T      3 = C L U
4 = D M V      5 = E N W      6 = F O X
7 = G P Y      8 = H Q Z      9 = I R
```

`system = "pythagorean"`. Vowels: `A E I O U`. `Y` is always a consonant.

---

## 5. Name Input Model

Required: `birth_first_names`, `birth_last_name`, `birth_date`.
Optional: `birth_middle_names`, `current_first_names`, `current_middle_names`,
`current_last_name`, `preferred_name`, `birth_time`, `birth_place`.

The Core (all FROZEN metrics below) is computed from the **full birth name**
(`birth_first_names` + `birth_middle_names` + `birth_last_name`, in that order, tokenized
into components per §3).

---

## 6. No-Vowels Edge Case

If the normalized full birth name contains no character from `A E I O U`:

```json
{
  "raw_value": 0, "root_value": 0, "master_number": null,
  "effective_value": 0, "display_value": "0"
}
```

with flag `{"code": "NO_VOWELS"}` attached to the Soul Urge metric. No exception is raised.
`first_vowel = null`. Personality still computes normally from consonants. The invariant
`expression.raw_value == soul_urge.raw_value + personality.raw_value` holds (Soul Urge
contributes 0).

---

## 7. Metric Flags

Structured only, never a free string:

```json
{"code": "KARMIC_DEBT", "value": "13/4", "source_raw_value": 13}
```
```json
{"code": "NO_VOWELS"}
```

---

## 8. Life Path — `metric_id="life_path"`, `method="segmented_v1"`

**Definition.** The segmented sum of independently-reduced birth-date segments.

**Formula.** `day`, `month`, `year` are each reduced independently via `reduce_compound`
(Master Numbers preserved per segment). Then:

```
life_path.raw = day.effective + month.effective + year.effective
life_path = reduce_compound(life_path.raw)
```

**Worked example (1986-07-18):** `day=18→9`, `month=7→7`, `year=1986→1+9+8+6=24→2+4=6`.
`9+7+6=22` → **`22/4`** (Master preserved).

**Edge Cases.** Any segment may itself resolve to a Master Number; its `effective_value`
(the master number, not its root) is what feeds the sum.

**Test Requirements.** Golden case above; property test that segment order (day/month/year)
does not change output given fixed values; edge cases for each segment individually hitting
11/22/33.

---

## 9. Life Path Direct Diagnostic (non-canonical)

`method="direct_digit_sum"`. Concatenate all digits of the ISO birth date and sum them
directly (no per-segment reduction), then `reduce_compound`. Stored under
`diagnostics.life_path.alternative_methods` — **never** presented as a second Life Path.

Example: `1+8+0+7+1+9+8+6=40` → `40/4`.

---

## 10. Birthday — `metric_id="birthday"`

**Formula.** `reduce_compound(day_of_month)`. Master preservation applies.
Example: `18 → "18/9"`.

---

## 11. Attitude — `metric_id="attitude"`

**Formula.** `reduce_compound(raw_calendar_month + raw_calendar_day)` — using the **raw**
month/day integers, not the pre-reduced Life-Path segments.
Example: `7 + 18 = 25 → "25/7"`.

---

## 12. Expression / Destiny — `metric_id="expression"`

**Formula.** Map every letter of `calculation_string` (full birth name, all components
concatenated) through the Pythagorean table, sum all values, then `reduce_compound`. No
per-name-component pre-reduction.

Example: `LUKAS=3+3+2+1+1=10`, `SPRINGER=1+7+9+9+5+7+5+9=52`, `10+52=62 → "62/8"`.

---

## 13. Soul Urge — `metric_id="soul_urge"`

**Formula.** Sum Pythagorean values of vowels (`A E I O U`) only in `calculation_string`,
then `reduce_compound`. No-Vowels edge case per §6 applies.

Example: `U=3, A=1, I=9, E=5 → 18 → "18/9"`.

---

## 14. Personality — `metric_id="personality"`

**Formula.** Sum Pythagorean values of consonants only (everything not a vowel, `Y`
included) in `calculation_string`, then `reduce_compound`.

**Invariant.** `expression.raw_value == soul_urge.raw_value + personality.raw_value`
(checked before reduction, on raw sums).

Example: `44 → "44/8"`.

---

## 15. Maturity — `metric_id="maturity"`

**Formula.** `reduce_compound(life_path.root_value + expression.root_value)` — uses **root**
values, not `effective_value` (i.e. Master effective values are not used here).

Example: `life_path 22/4 → root 4`, `expression 62/8 → root 8`, `4+8=12 → "12/3"`.

---

## 16. Balance — `metric_id="balance"`

**Formula.** Sum the Pythagorean value of the **first letter of each structural birth-name
component** (from `normalization.components`, not `calculation_string`), then
`reduce_compound`.

Example: `LUKAS→L=3`, `SPRINGER→S=1`, `3+1=4` → `4`.

Hyphenated/multi-part names must yield multiple components and therefore multiple
first-letter contributions.

---

## 17. Hidden Passion — special schema

**Formula.** Count frequency of each Pythagorean value `1..9` across `calculation_string`.
Result is the set of value(s) with maximum frequency (ties are **never** broken — all tied
values are returned) plus that frequency, `values` sorted ascending.

```json
{"values": [1, 9], "frequency": 3}
```

---

## 18. Karmic Lessons — special schema

**Formula.** The Pythagorean values `1..9` that have **zero** occurrences in
`calculation_string`, sorted ascending: `[4, 6, 8]`.

---

## 19. Subconscious Self — `metric_id="subconscious_self"`

**Formula.** Count of distinct Pythagorean values `1..9` present at least once in
`calculation_string`.

**Invariant.** `subconscious_self + len(karmic_lessons) == 9`.

---

## 20. Intensity Table

Always all nine keys `"1".."9"` with actual counts (zero-filled), never sparse.

---

## 21. Karmic Debt

Recognized **only**: `13/4`, `14/5`, `16/7`, `19/1` — set only when the canonical
`raw_value` is **exactly** `13`, `14`, `16`, or `19` (not e.g. `31`, and not merely present
somewhere in an internal trace).

**Allowlist for automatic flagging:** `life_path`, `birthday`, `expression`, `soul_urge`,
`personality` only. A Pinnacle showing `13/4` may be *displayed* as that compound but never
receives the automatic Core Karmic Debt flag.

---

## 22. Cornerstone / Capstone / First Vowel

- Cornerstone: first alphabetic letter of the full normalized birth name (`calculation_string[0]`).
- Capstone: last alphabetic letter (`calculation_string[-1]`).
- First Vowel: first vowel character in `calculation_string`, or `null` if none.

---

## 23. Birth Segments

`birth_month_segment`, `birth_day_segment`, `birth_year_segment` — each a `ReductionResult`
with `source_value` set to the raw calendar component (e.g. year `1986`). The intermediate
compound (e.g. year `1986 → 24`) is retained in `reduction_steps`.

---

## 24. Pinnacles — `method="segmented_v1"`

- **P1** = `reduce_compound(birth_month_segment.effective + birth_day_segment.effective)`
- **P2** = `reduce_compound(birth_day_segment.effective + birth_year_segment.effective)`
- **P3** = `reduce_compound(P1_contribution + P2_contribution)` where each contribution is
  the **root** of P1/P2 if non-master, or the **effective_value** (master number) if P1/P2 is
  a master.
- **P4** = `reduce_compound(birth_month_segment.effective + birth_year_segment.effective)`

Worked example: `P1=7+9=16→"16/7"`, `P2=9+6=15→"15/6"`, `P3=7+6=13→"13/4"`,
`P4=7+6=13→"13/4"`.

**Historical diagnostic compounds** (e.g. `7+18=25/7`, `18+24=42/6`) are stored under
`diagnostics.pinnacles.alternative_methods` and are never canonical. UI must visually
distinguish `Canonical` vs `Diagnostic`.

**Age boundaries.** `first_end_age = 36 - life_path.root_value` (integer). Windows:
`P1: [0, first_end_age]`, `P2: [first_end_age+1, first_end_age+9]`,
`P3: [first_end_age+10, first_end_age+18]`, `P4: [first_end_age+19, ∞)`. Boundaries are
computed as concrete calendar dates (birth date + N years), never floating-point ages.
Leap-day rule: for a person born on Feb 29, an anniversary falling in a non-leap year is
Feb 28.

---

## 25. Challenges — root values only, no master classification

```
month = birth_month_segment.root_value
day   = birth_day_segment.root_value
year  = birth_year_segment.root_value

challenge_1 = abs(day - month)
challenge_2 = abs(day - year)
challenge_3 = abs(challenge_1 - challenge_2)
challenge_4 = abs(month - year)
```

Example: `month=7, day=9, year=6` → `2, 3, 1, 1`. `0` is a valid Challenge value. No Master
Number classification is applied to Challenge results.

---

## 26. Period Cycles

`period_1 = birth_month_segment`, `period_2 = birth_day_segment`, `period_3 =
birth_year_segment` (values only). Age-boundary transitions for Period Cycles are
`RESERVED_UNFROZEN` — implement the values, never invented transition ages in UI or engine.

---

## 27. Universal Year

`source_value = gregorian_year`, `raw_value = digit_sum(gregorian_year)`, then
`reduce_compound(raw_value)`. Example: `2026 → 2+0+2+6=10 → "10/1"`.

---

## 28. Personal Year

`reduce_compound(birth_month_segment.effective + birth_day_segment.effective +
universal_year.effective)`. Validity model: `01.01.–31.12.` of the target calendar year — no
birthday-transition model in V1.

Example (2026): `7+9+1=17 → "17/8"`.

---

## 29. Personal Month / Personal Day

`personal_month = reduce_compound(personal_year.effective + calendar_month.effective)` where
`calendar_month.effective` is `reduce_compound(calendar_month)`. If Personal Year is a
Master, its master value is used directly in the sum.

`personal_day = reduce_compound(personal_month.effective + calendar_day.effective)`.

---

## 30. As-Of Date / Future Birth Dates

The engine never calls `date.today()`; every time-dependent function requires `as_of_date`.
The engine itself accepts any syntactically valid Gregorian date, including future dates —
it has no concept of "today". The **application/API layer** rejects person profiles whose
birth date is after "today" in `APP_TIMEZONE` (default `Europe/Berlin`) with error code
`FUTURE_BIRTH_DATE_NOT_ALLOWED`. This is an application-layer rule, not an engine rule.

---

## 31. Birth Time / Birth Place — `METADATA_ONLY`

Neither affects any Core numerology metric in V1. Birth time: `{"value": "06:00:00",
"precision": "exact"|"approximate"|"unknown"}`. Birth place: `display_name`,
`country_code?`, `latitude?`, `longitude?`, `timezone?`. No geocoding inside
`engine-numerology`.

---

## 32. Astrology — `FEATURE_DISABLED_NO_CANON`

`packages/engine-astrology` exists as an interface only. No astrological calculation is
implemented or presented as available in V1.

---

## 33. Unfrozen Features (`RESERVED_UNFROZEN` / `FEATURE_DISABLED_NO_CANON`)

Essence, Name Transits, Physical/Mental/Spiritual Transit, Planes of Expression,
Relationship compatibility percentage, Period Cycle date boundaries, Astrology. Interface
and/or flag only — never a fabricated formula or fake percentage.

---

## 34. Canonical Metric Model

```python
class MetricFlag(BaseModel):
    code: str
    value: str | None = None
    source_raw_value: int | None = None


class ReductionResult(BaseModel):
    source_value: int | None
    raw_value: int
    root_value: int
    master_number: int | None
    effective_value: int
    display_value: str
    reduction_steps: list[int]


class CalculationMetric(BaseModel):
    metric_id: str
    system: str
    method: str
    source_value: int | str | None
    raw_value: int
    root_value: int
    master_number: int | None
    effective_value: int
    display_value: str
    calculation_trace: CalculationTrace
    flags: list[MetricFlag]
```

`CalculationTrace` carries `input_refs`, `normalization` block, and an ordered
`operations` list (`letter_mapping` / `sum` / `reduce` steps) with machine-truth operand
lists — display strings such as `"9 + 7 + 6"` are generated *from* the trace, never the other
way around.

---

## 35. Canonical Profile JSON — top-level shape

```json
{
  "schema_version": "1.0.0",
  "calculation_system": "numra-canonical",
  "calculation_version": "1.0.0",
  "person": {},
  "normalization": {},
  "core_numbers": {
    "life_path": {}, "birthday": {}, "attitude": {}, "expression": {},
    "soul_urge": {}, "personality": {}, "maturity": {}, "balance": {},
    "hidden_passion": {}, "karmic_lessons": {}, "subconscious_self": {},
    "cornerstone": {}, "capstone": {}, "first_vowel": {}, "intensity_table": {}
  },
  "cycles": {"period_cycles": {}, "pinnacles": {}, "challenges": {}},
  "timing": {},
  "diagnostics": {},
  "warnings": []
}
```

See `specs/profile.schema.json` for the enforced JSON Schema.

---

## 36. Golden Reference — Lukas Springer

See `fixtures/canonical/lukas-springer.v1.json`. Input: Lukas Springer, 1986-07-18, 06:00
(exact), Meerbusch. All values in this document's worked examples derive from this person and
MUST match the fixture exactly, including full calculation traces.

## 37. Anti-Cheating Rule

Production code (`packages/engine-numerology/src/**`) MUST NOT import fixture files, MUST
NOT compare against the literal string `"Lukas"`/`"Springer"`, and MUST NOT contain the
literal birth date `1986-07-18`/`18.07.1986` or any golden numeric result as a lookup
shortcut. A repository test (`test_no_golden_leakage`) statically greps production source for
these tokens and fails the build if found.
