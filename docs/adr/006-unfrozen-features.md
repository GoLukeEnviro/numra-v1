# ADR 006 — Unfrozen Features Get an Interface, Never a Guessed Formula

## Status

Accepted.

## Context

Several numerology concepts referenced by the wider field — Essence, Name/Physical/
Mental/Spiritual Transits, Planes of Expression, a relationship compatibility
percentage, Period Cycle date boundaries, and astrology generally — have no single
agreed formula, or NUMRA V1 simply has no verified canon for them yet. The project's
core rule, stated plainly in the master prompt, is "NUMRA DOES NOT GUESS": inventing a
formula because it looks plausible would silently manufacture false precision.

## Decision

Every such feature is marked `RESERVED_UNFROZEN` or `FEATURE_DISABLED_NO_CANON` in
`specs/canon-spec.md` and implemented, at most, as a typed interface that raises
`NotImplementedError` when called — never a fabricated calculation, never a fake
percentage. Concretely:

- `packages/engine-astrology` exposes `AstrologyEngineInterface.compute()`, which
  always raises; `CanonicalPerson`-equivalent metadata (birth date/time/place,
  timezone) is already shaped to be handable to a real astrology engine later, but no
  astrological value is computed or displayed anywhere in V1.
- Relationship comparison (`relationship_service.py`) compares only the exact metric
  pairs canon-spec.md §59 allows (Life Path, Expression, Soul Urge, Personality,
  Maturity, Personal Year/Month/Day) and reports `match: bool` per pair — no
  compatibility percentage exists anywhere in the API response or the frontend.
- Period Cycle *values* are implemented (they're just the birth-date segments); Period
  Cycle *age-boundary transitions* are not — the frontend is expected to never invent
  transition ages either.

## Consequences

- A future PR that adds a real astrology canon or a verified compatibility-percentage
  formula is purely additive — it doesn't need to retract a previously-shipped guess.
- Anyone auditing the codebase for "does this claim more precision than it has" can
  grep for `RESERVED_UNFROZEN`/`FEATURE_DISABLED_NO_CANON` and get a complete list.
- Product pressure to "just add a percentage, users expect one" is a decision this ADR
  puts in front of a person, not something an agent or a future contributor can slip in
  as an implementation detail.
