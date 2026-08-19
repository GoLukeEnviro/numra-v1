# Phase 3 Evidence — Knowledge System, Interpretation Engine, LLM Adapter

Built by a delegated build agent working exclusively inside `knowledge/` and
`packages/engine-interpretation/`, then independently re-verified (commands re-run) before
being committed alongside Phase 2.

| Item | Status |
|---|---|
| `knowledge/manifest.yaml` + numbers 1-9 + masters 11/22/33 (German seed content, verbatim per master prompt §88) | PASS |
| `knowledge/karmic-debts/{13-4,14-5,16-7,19-1}.yaml` | PASS |
| `knowledge/metrics/*.yaml` (16 metric contexts, each textually distinct) | PASS |
| All 33 YAML files parse and validate against typed pydantic models | PASS |
| `numra_interpretation` composes a structured `Interpretation` from `CanonicalProfile` + Knowledge, no calculation | PASS |
| `LLMProvider` protocol, `MockLLMProvider` (deterministic, no network), `OllamaCloudProvider` (real httpx client, env-configured, bounded retries, clean "unavailable" when unconfigured) | PASS |
| Numeric-claims validator (per-claim linter) — wrong claim / unknown metric_id both raise `InvalidReportSection` | PASS |
| ruff format / ruff check / mypy strict | PASS |
| pytest | PASS — 51 passed |

## Commands re-run for independent verification

```text
$ find knowledge -name "*.yaml" | wc -l
33

$ uv run pytest packages/engine-interpretation/tests -q
51 passed in 0.61s

$ uv run mypy packages/engine-interpretation/src   (as part of the combined command in phase-2.md)
Success: no issues found in 77 source files

$ uv run ruff check packages/engine-interpretation
All checks passed!
```

## Post-hoc fix applied outside the delegated agent's scope

The delegated agent correctly scoped `# type: ignore[import-untyped]` on `numra_numerology`
imports because that package shipped no PEP 561 `py.typed` marker at the time — it was
explicitly instructed not to touch `packages/engine-numerology`. After Phase 2 work added
`py.typed` markers to `numra_numerology` and `numra_interpretation` (see phase-2 commit),
those three `type: ignore` comments became genuinely unused (`mypy --warn-unused-ignores`
flagged them) and were removed as a small follow-up cleanup — no logic changed.

## Judgment calls made explicit (from the delegated agent's own report, spot-checked)

- **`strengths` field**: the master prompt's seed text only distinguishes `core_themes` and
  `shadows`; `strengths` (required by the knowledge schema in §87) was authored as a short,
  theme-consistent elaboration distinct from the raw `core_themes` word list, for every
  number/master file.
- **Scope of composed sections**: `compose_interpretation` covers the 8 `CoreNumbers` fields
  that are uniform `CalculationMetric` instances (life_path, birthday, attitude, expression,
  soul_urge, personality, maturity, balance). The other 7 `core_numbers` entries
  (hidden_passion, karmic_lessons, subconscious_self, cornerstone, capstone, first_vowel,
  intensity_table) have structurally different shapes (multi-value sets, letters, a bare
  count, a zero-filled table) and are explicitly left for a later phase rather than forcing
  a mismatched uniform template onto them.
- **`KnowledgeBase.karmic_debt()`** returns `None` for compounds outside
  `{13/4,14/5,16/7,19/1}` (expected/common case per canon-spec.md §21) vs. raising `KeyError`
  for a genuinely unknown number/metric id — an intentional asymmetry, not an oversight.
- **`MockLLMProvider.generate_structured`** recognizes conventional field names
  (`text`/`text_de`, `numeric_claims`, `metric_id`) on the caller-supplied schema and fills
  them from the request; any other required field with no default raises `ValueError` rather
  than fabricating a value.

## Not yet built (explicitly out of Phase 3 scope, deferred)

- The full multi-section **Report Numerical Linter** (cross-section consistency,
  `MissingSections`/`DuplicateHeadings`/word-count checks) — only the per-claim validator
  exists so far; the rest is Phase 4 (§109, tied to the report assembly pipeline).
- Live Ollama Cloud smoke test — **NOT VERIFIED / EXTERNAL_DEPENDENCY_NOT_AVAILABLE**
  (no `OLLAMA_API_KEY` configured in this environment). The adapter's `health()` correctly
  reports `"unavailable"` in that case rather than crashing, which is the requirement for
  this phase; live generation against a real Ollama Cloud endpoint is unverified.
