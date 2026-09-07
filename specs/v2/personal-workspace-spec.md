# AVENYTH V2 — Personal Workspace Spec

## Status

Draft — Phase 0 spec freeze.

## Principle

The Personal Workspace is built **around** the existing `Person`/`Calculation`
model. It does not duplicate `CanonicalProfile`. A `Calculation` stays an immutable
snapshot (ADR from V1.5, `docs/adr/007-v1-5-product-completion.md`) — the Personal
Workspace reads from it, never forks it.

## Sections

```
PROFILE
CORE NUMBERS
STRENGTHS
SHADOWS
DEVELOPMENT
RELATIONSHIPS
COMMUNICATION
NEEDS
WORK / EXPRESSION
TIMING
PINNACLES
CHALLENGES
KARMIC LESSONS
HIDDEN PASSION
REPORTS
PRIVATE REFLECTIONS
PRIVATE NOTES
PRIVATE TASKS
PRIVATE COPILOT
```

`PROFILE` through `HIDDEN PASSION` and `TIMING` render from the existing
`CanonicalProfile` + Knowledge Base pipeline already shipped for V1 reports/Today —
no new calculation logic. `REPORTS` reuses the existing report job/PDF pipeline.
`TIMING` reuses existing Today/Daily-Brief data verbatim, not a re-derivation.

`PRIVATE REFLECTIONS`, `PRIVATE NOTES`, `PRIVATE TASKS`, `PRIVATE COPILOT` are new
V2 surfaces, scoped `PERSONAL_PRIVATE` (never shared unless the user explicitly
performs a `SHARE` action into a relationship context — see
`specs/v2/task-system-spec.md` §Shared Reflection semantics and
`specs/v2/copilot-grounding-spec.md`).

## Applies-to-self default

A user's own `SELF` profile is the default Personal Workspace target. A
`MANAGED_MINOR`/`MANAGED_OTHER` profile the same account owns can have its own
Personal Workspace (`PROFILE` through `TIMING`, `REPORTS`), but never gets
`PRIVATE_COPILOT`, `PRIVATE_TASKS` proposals from other users, or any section that
implies a relationship connection to another account
(`specs/v2/minor-profile-policy.md`).

## Non-goals

No new `CanonicalProfile` schema. No new calculation engine. No compatibility
scoring inside the Personal Workspace.
