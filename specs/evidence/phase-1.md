# Phase 1 Evidence — Deterministic Engine

| Item | Status |
|---|---|
| `ruff format --check .` | PASS |
| `ruff check .` | PASS |
| `mypy` (strict, engine-numerology + engine-astrology + engine-interpretation) | PASS |
| `pytest` (packages/engine-numerology/tests) | PASS — 104 passed |
| Coverage (`--cov=numra_numerology --cov-fail-under=90`) | PASS — 100% |
| Hypothesis property tests | PASS (termination, root range, master range, no-false-master, master preservation, expression invariant, subconscious/karmic-lessons invariant, hash reproducibility, intensity-table shape) |
| Golden Lukas Springer test (values + traces) | PASS |
| Reduction test matrix (§Reduction Test Matrix) | PASS — all 15 pairs |
| Edge-case fixtures (§71) | PASS — master birthday 11/22, 44/55 compounds, leap-day Feb 29, multiple first names, hyphenated name, apostrophe name, Ä/Ö/Ü/ß/é/ñ, vowel-less name, Hidden Passion tie + unique, no Karmic Lessons, multiple Karmic Lessons, Challenge = 0 |
| Anti-cheating (§37) — no golden-fixture literals/imports in `src/**` | PASS |
| Engine output validates against `specs/profile.schema.json` | PASS |

## Commands run

```text
$ uv run pytest packages/engine-numerology/tests -q --cov=packages/engine-numerology/src/numra_numerology --cov-report=term-missing --cov-fail-under=90
...
TOTAL   600   0   100%
Required test coverage of 90% reached. Total coverage: 100.00%
104 passed in 2.30s

$ uv run ruff format --check .
9 files would be reformatted -> ran `uv run ruff format .` -> re-checked clean

$ uv run ruff check .
All checks passed!

$ uv run mypy packages/engine-numerology/src packages/engine-astrology/src packages/engine-interpretation/src
Success: no issues found in 32 source files

$ uv run python3 -c "... jsonschema.validate(engine_output, profile.schema.json) ..."
Engine output validates against schema: OK
deterministic_hash: 869f161a080f19fdb8ffc70eeb06466982fc6c35b3d3e9f4371dfef4149d1936
```

## Notes / judgment calls made explicit

- **"Other typographic punctuation is stripped"** (canon-spec.md §3): the master prompt does
  not enumerate which punctuation beyond the declared separator set counts as "admissible."
  Implemented as: any Unicode punctuation character (category `P*`) that is not one of the
  declared tokenization separators is silently dropped before component formation (e.g.
  `"St. Martin"` → components `("ST", "MARTIN")`). Digits and letters from unsupported
  scripts are deliberately **not** silently dropped — they fail A-Z validation and raise
  `NORMALIZATION_UNSUPPORTED_SCRIPT`, per the "NUMRA does not guess" / no-silent-fallback
  principle (master prompt §156, §173).
- **Pinnacle age windows**: implemented as concrete calendar dates. Convention chosen (not
  specified verbatim in the master prompt): each window's `end_date` equals the *next*
  window's `start_date` (the exact birthday-transition instant), computed via `birth_date +
  (end_age + 1)` years, with the Feb 29 → Feb 28 leap-day rule applied on that arithmetic.
  `windows` was added to `specs/profile.schema.json`'s `Pinnacles` definition (not in the
  original schema draft) to carry this.
- `packages/engine-interpretation` and `packages/engine-astrology` contain only the
  placeholder interfaces required for the workspace to resolve at this phase (astrology is
  `FEATURE_DISABLED_NO_CANON`); their real implementation is Phase 3.
- Period Cycle age-boundary transitions are intentionally **not** implemented (`RESERVED_UNFROZEN`,
  canon-spec.md §26) — only the three period values themselves.
