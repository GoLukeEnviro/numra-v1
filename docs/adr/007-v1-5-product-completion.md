# ADR 007 — V1.5 Product Completion: New Durable Decisions

## Status

Accepted.

## Context

V1.5 ("NUMRA V1.5 — Product Completion") added fourteen product epics on top of the
frozen V1 canon: server-authoritative history, a complete editable person profile,
real identity history, a report library, a relationship library, relationship
intelligence v2, i18n, a mobile bottom nav, a PWA, an expanded deterministic
interpretation engine, a deterministic Daily Brief, calculation snapshot comparison,
report provenance, and Settings V2. None of it touches `calculation_version` or the
golden canon (re-verified: 22/22 golden tests pass unchanged throughout). Several of
these epics made decisions durable enough — and easy enough to accidentally undo in a
later change — to record here rather than leave implicit in the diff.

## Decisions

### Server is authoritative; LocalStorage is a convenience, never a requirement

Before V1.5, `local-calculations.ts`/`local-reports.ts`/`local-relationships.ts` were
the *only* way the frontend discovered a user's own history — a fresh browser context
with no LocalStorage saw nothing. New list endpoints
(`GET /v1/people/{id}/calculations`, `GET /v1/reports`, `GET /v1/relationships`) make
the server the source of truth; `local-reports.ts`/`local-relationships.ts` were
deleted outright. `local-calculations.ts`/`local-preferences.ts` remain, but only for
genuinely presentational conveniences (e.g. which person the Today page last opened
to) that are always re-validated against what the API actually returns — never the
sole way to discover that a record exists.

### A `Calculation` snapshot is immutable; editing a `Person` never rewrites one

`repositories/calculations.py` has no update function, and Epic B added an explicit
test (`test_editing_person_never_mutates_existing_calculations`) proving that editing
birth data after a calculation exists leaves that calculation's `deterministic_hash`
and `canonical_profile` byte-identical. `NameIdentity` rows are append-only in the
same spirit (`sync_identity_history` only ever inserts a new row when the proposed
value actually differs from the latest one of that kind — never rewrites or deletes
history), and `valid_from` is only ever set from a genuinely known fact (a birth
identity's `valid_from` = the birth date) — never invented for current/preferred
entries, which carry `recorded_at` only.

### No relationship compatibility score, ever — reaffirms ADR 006, extended

Epic F added knowledge-sourced "Relationship notes" (per-metric qualitative themes,
composed from each person's already-computed number and `knowledge/numbers/*.yaml`'s
existing `relationships` field) without adding any numeric match score, percentage, or
ranking. This is the same `RESERVED_UNFROZEN` boundary ADR 006 established for the
original pairwise comparison — extended, not loosened. A `RelationshipInsightOut` has
no field that could hold one; a test asserts as much explicitly.

### The Daily Brief is deterministic and reflective, never predictive or LLM-generated

`numra_interpretation.daily_brief.compose_daily_brief()` composes Personal Day/Month/
Year text purely by reusing `compose_section()` against already-computed profile
values and `knowledge/`. Given the same profile and knowledge version, it always
returns a byte-identical result — no LLM call, no randomness, no wall-clock dependency
beyond the `as_of_date` the caller explicitly passed. The composed language is
reflective/symbolic ("wird ... gedeutet", "kann"), never phrased as a guaranteed
outcome — enforced by a test asserting the output never contains phrases like "wird
passieren" or "garantiert".

### The service worker never caches anything under `/api/`

`public/sw.js`'s fetch handler bypasses (returns without intercepting) any request
whose path starts with `/api/` — Numra's same-origin backend proxy, which carries
session-authenticated personal data (profiles, calculations, reports) — before any
cache logic runs. Only immutable, versioned static assets (`_next/static/*`, icons,
the manifest) are ever cached; page navigations are network-only. This is enforced by
a static-source test (the bypass must precede any `respondWith` call) and was verified
against a live server with real authenticated traffic: after logging in and navigating
several pages, an audit of every Cache Storage entry confirmed zero were under `/api/`.
A future change that adds a broader caching strategy must preserve this boundary, not
just avoid regressing test coverage of it.

### Interface language is independent of knowledge/report language

`src/i18n/` governs only UI chrome copy (nav labels, Settings, etc.) and defaults to
German with an explicit, persisted per-browser switch to English. It does not, and
must not, influence which language `knowledge/` content or a generated report is
written in (currently German-only) — those are a separate axis entirely. Conflating
the two would make "switch to English" silently change what a report's actual
numerological content claims, which is not what a UI language preference means.

## Consequences

- Any future change to the service worker, the Daily Brief composer, or the
  relationship-insights schema should treat the boundaries above as load-bearing, not
  incidental — a reviewer can point at this ADR rather than re-deriving the rationale.
- The immutability guarantees (calculation snapshots, append-only identity history)
  are safe to build further features on (e.g. audit trails, undo) without worrying
  that some other code path might quietly rewrite history first.
- `RESERVED_UNFROZEN` (ADR 006) is confirmed as the standing default for any future
  "give me one number that captures how well two people match" request — V1.5 had
  every opportunity to add one and deliberately built the opposite (per-metric,
  no-score) instead.
