# AVENYTH V2 — API Contract

## Status

Draft — Phase 0 spec freeze. Exact request/response schemas are finalized per-PR
and reflected in the OpenAPI spec + generated TS types (existing
`schema-and-openapi-drift` CI check stays mandatory).

## Auth extensions (existing opaque server-side sessions stay authoritative)

No move to JWT/OAuth/OIDC/refresh-token architecture for V2 Web. New routes:

```
POST /v1/auth/request-email-verification
POST /v1/auth/verify-email
POST /v1/auth/forgot-password
POST /v1/auth/reset-password
```

Token model: random cryptographically secure token, only the hash persisted,
single use, expiry, replay protection, rate limiting — mirrors the existing
session-token handling in `apps/api/src/numra_api/auth/`.

Anti-enumeration: the forgot-password response never reveals whether an account
exists for the given email. A successful password reset revokes all of that
account's existing sessions.

## Entitlements

```
GET /v1/me/entitlements
```

Server-authoritative; no scattered `if premium`/`if subscription`/`if plan == ...`
checks anywhere in route or service code. Example entitlement keys:

```
personal_workspace
connections
relationship_workspaces
relationship_checkins
relationship_copilot
advanced_relationship_analysis
life_tracking
premium_reports
max_connections
max_workspaces
```

Beta default: everything unlocked. Payment provider integration is explicitly
out of scope for V2 Core (`specs/v2/architecture.md`).

## Primary navigation (Web/PWA)

```
Home
Profile
Connections
Workspaces
Today
Copilot
Settings
Admin        (ADMIN role only)
```

Relationship Workspace tabs:

```
Overview
Dynamics
Check-in
Tasks
Roadmap
Journal
Copilot
```

## Observability (metrics, never content)

```
connections_invited_total
connections_accepted_total
connections_declined_total
connections_revoked_total
relationship_workspaces_active
relationship_workspaces_dissolved
consent_granted_total
consent_revoked_total
checkins_submitted_total
checkins_completed_pair_total
tasks_proposed_total
tasks_accepted_total
tasks_completed_total
roadmaps_created_total
copilot_requests_total
copilot_validation_failures_total
llm_latency_ms
llm_token_usage
llm_estimated_cost
```

Never logged: journal contents, chat text, private notes, raw birth profile
content (`specs/v2/privacy-spec.md`).

## PR structure (Section 53)

```
PR-V2-00  Specs + ADRs + PR #15 resolution                (this phase)
PR-V2-01  Brand + auth + entitlements
PR-V2-02  Personal Workspace
PR-V2-03  Connections + consent
PR-V2-04  Relationship Workspace Core
PR-V2-05  Relationship/Shadow Analysis
PR-V2-06  Configurable Check-ins
PR-V2-07  Tasks
PR-V2-08  Roadmaps + Shared Reflection
PR-V2-09  Private + Shared Copilot
PR-V2-10  Dissolution + Account Deletion + Privacy Closure
PR-V2-11  Evidence Layer
PR-V2-12  Native Mobile
```

Every PR: starts from current `main`, stays focused, contains tests, contains a
migration if schema changed, regenerates OpenAPI/TS types if the contract changed,
updates documentation, passes all 12 existing required checks plus any new
phase-specific check, and never alters the frozen canon without a separately
approved canon-change ADR.
