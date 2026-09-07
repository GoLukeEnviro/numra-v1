# ADR 010 — Directional, Versioned, Revocable Consent; RLS Deferred

## Status

Accepted.

## Context

Sharing numerology/relationship data between two independent accounts requires an
explicit permission model — "we're connected" cannot imply "everything is shared."
Frontend-only hiding is not security; every access must be checked server-side.
PostgreSQL Row-Level Security was considered as a defense-in-depth layer on top of
existing API-level authorization.

## Decision

Consent is modeled as `ConsentGrant`/`ConsentEvent` rows: directional (grantor →
grantee, independent of the reverse direction), versioned (bound to the scope
taxonomy version active at grant time), auditable (every grant/revoke is an event),
and immediately revocable — no cache lag, no grace period
(`specs/v2/consent-spec.md`).

Default grants at connection setup are `CORE_NUMEROLOGY`, `RELATIONSHIP_INSIGHTS`,
`CURRENT_TIMING`. `PRIVATE_JOURNAL`, `PRIVATE_TASKS`, `PRIVATE_COPILOT`,
`OTHER_RELATIONSHIPS`, `LIFE_TRACKING` are opt-in only, per direction.

Row-Level Security is **deferred for V2 Core**: the codebase's existing
SQLAlchemy/repository-layer authorization pattern (checked in every route/service,
tested via the two-user IDOR matrix) is judged adequate for launch, and introducing
RLS now risks destabilizing established query patterns without a demonstrated gap.
Application-level authorization remains mandatory regardless, and RLS adoption can
be revisited as a later, separately reviewed hardening pass once V2 Core's access
patterns are stable and battle-tested via the IDOR matrix.

## Consequences

- Every new V2 route/service must implement its own explicit authorization check;
  there is no RLS safety net to catch an omitted check in V2 Core.
- The two-user authorization matrix (`specs/v2/privacy-spec.md`) is a required,
  repeated test, not a one-time check — it is re-run for every new surface.
- If RLS is adopted later, it will be an explicit follow-up ADR, not a silent
  addition.
