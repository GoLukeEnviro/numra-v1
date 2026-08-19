# ADR 002 — Canonical/Schema/Knowledge/Prompt Versioning

## Status

Accepted.

## Context

Four independent things can change over the life of this project: the calculation
rules themselves, the JSON shape a `CanonicalProfile` is serialized as, the German
interpretive content in `knowledge/`, and the report-generation prompt. Conflating any
of these into a single version number would make it impossible to answer "was this
report reproducible" or "did this person's numbers change because of a bug fix or
because we reinterpreted the text around them."

## Decision

Four separate version identifiers, each bumped independently:

- `calculation_version` (`numra_numerology`) — PATCH for a fix with no output change,
  MINOR for an additive new metric that doesn't touch existing ones, MAJOR for anything
  that changes an existing person's existing numbers (canon-spec.md §157).
- `schema_version` — the `CanonicalProfile` JSON shape.
- `knowledge_version` (`knowledge/manifest.yaml`) — interpretive content only; never
  moves the calculation version.
- `prompt_version` (e.g. `numra-report-v1`) — the report-generation instruction set.

A `Report` row persists all four (plus `model_provider`/`model_name`), so any report
can later be traced back to exactly which calculation rules, schema, knowledge text,
and prompt produced it — independent of when it was viewed.

## Consequences

- A knowledge-content copy edit never requires re-validating the golden numeric fixture.
- A calculation bug fix is visible in diffs as a `calculation_version` bump and forces
  an explicit decision about whether existing persisted `Calculation` rows are still
  valid under the new version (they are immutable snapshots, so old ones stay tagged
  with the version that produced them rather than being silently reinterpreted).
- Report reproducibility is auditable without needing external logs.
