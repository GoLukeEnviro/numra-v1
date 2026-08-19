# Phase 0 Evidence — Canon Specification

| Item | Status |
|---|---|
| `specs/canon-spec.md` present, documents every FROZEN-V1 rule (Definition/Input/Normalization/Formula/Reduction Boundary/Master Rule/Output/Trace/Edge Cases/Test Requirements per metric) | PASS |
| `specs/profile.schema.json` present and valid | PASS (see command below) |
| Lukas Springer golden fixture present (`fixtures/canonical/lukas-springer.v1.json`) | PASS |
| Fixture validates against schema | PASS (see command below) |
| All UNFROZEN rules explicitly blocked (`RESERVED_UNFROZEN` / `FEATURE_DISABLED_NO_CANON`) | PASS — canon-spec.md §26, §32, §33 |
| Display-value rule documented verbatim | PASS — canon-spec.md §2 |
| No-Vowels rule documented | PASS — canon-spec.md §6 |
| Name components (structured, not just concatenation) documented | PASS — canon-spec.md §3, §5 |
| Karmic Debt flags + allowlist documented | PASS — canon-spec.md §21 |
| Future-birth-date engine/application split documented | PASS — canon-spec.md §30 |

## Commands run

```text
$ uv sync --all-packages --all-groups
Installed 8 packages (pydantic, jsonschema, ruff, mypy, pytest, hypothesis, ...)

$ uv run python3 -c "
import json, jsonschema
schema = json.load(open('specs/profile.schema.json'))
fixture = json.load(open('fixtures/canonical/lukas-springer.v1.json'))
jsonschema.validate(fixture, schema)
print('Fixture validates against schema: OK')
"
Fixture validates against schema: OK
```

## Notes

- All numeric values in the golden fixture were hand-derived from the canon-spec formulas
  (not copied from the master prompt's worked examples) and cross-checked against every
  worked example given in the master prompt; they agree exactly, including intermediate
  traces (e.g. `LUKAS=10`, `SPRINGER=52`, Personality raw `44`, Pinnacle 3/4 both `13/4`,
  Challenges `2,3,1,1`, Personal Year 2026 `17/8`).
- `deterministic_hash` is intentionally omitted from the static fixture in this phase — it
  depends on the hash envelope implementation built in Phase 1. The Phase 1 golden test
  computes it from the engine and asserts the rest of the fixture's fields still match
  byte-for-byte.
- `as_of_date` used for the `timing` block in the fixture is `2026-08-19` (an arbitrary but
  fixed date within the 2026 Personal Year window), not the birth date — Personal Month/Day
  are date-dependent per §29 of the canon spec.
