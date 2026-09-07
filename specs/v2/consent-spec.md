# AVENYTH V2 — Consent Spec

## Status

Draft — Phase 0 spec freeze. Frozen decisions: #7 (default sharing), #9 (raw
answers stay private), #11 (dissolution retains shared artifacts).

## Consent scopes

```
CORE_NUMEROLOGY
RELATIONSHIP_INSIGHTS
CURRENT_TIMING
PRIVATE_JOURNAL
PRIVATE_TASKS
PRIVATE_COPILOT
OTHER_RELATIONSHIPS
LIFE_TRACKING
```

## Default grants at connection setup

Granted by default:

```
CORE_NUMEROLOGY
RELATIONSHIP_INSIGHTS
CURRENT_TIMING
```

Never granted by default (must be explicitly opted in per-direction):

```
PRIVATE_JOURNAL
PRIVATE_TASKS
PRIVATE_COPILOT
OTHER_RELATIONSHIPS
LIFE_TRACKING
```

## Model

```
ConsentGrant
  id, workspace_id, grantor_user_id, grantee_user_id, scope, granted_at,
  revoked_at (nullable), version

ConsentEvent
  id, grant_id, event_type (GRANTED | REVOKED), actor_user_id, occurred_at
```

Every grant is:

- **Directional** — Luke sharing `CURRENT_TIMING` with Sarah says nothing about
  Sarah sharing it with Luke; each direction is its own `ConsentGrant` row.
- **Versioned** — a grant references the scope taxonomy version active when it was
  created, so a later scope redefinition doesn't retroactively reinterpret it.
- **Auditable** — every grant/revoke is a `ConsentEvent`.
- **Revocable** — at any time, unilaterally, by the grantor only.

Example (Section 13): Luke grants Sarah `CURRENT_TIMING`. Sarah revokes her own
grant of `CURRENT_TIMING` to Luke. Luke's grant to Sarah is untouched — revocation
is per-direction, per-grantor.

## Enforcement

Frontend hiding is never security. Every data access checks, server-side, on every
request:

```
current_user
workspace_membership
consent_scope (grantor -> requester, for the specific resource's scope)
resource ownership
workspace state (not DISSOLVED, for anything beyond read-only historical artifacts)
```

Revocation is effective **immediately** — no cache lag, and no new inference may be
generated using data whose consent was revoked before the inference request, even
if an older inference generated while consent was active remains readable
(`specs/v2/dissolution-policy.md`).

## Acceptance checks

- Granting/revoking a scope is reflected in the very next request (no TTL/cache
  window).
- A `ConsentEvent` exists for every grant and every revoke.
- Two-user IDOR matrix: User B can never read a scope User A has not granted them,
  regardless of workspace membership.
- After Sarah revokes `CURRENT_TIMING`, a request from Luke for a timing-based
  Copilot answer about Sarah fails closed (falls back to `INSUFFICIENT_EVIDENCE`
  classification per `specs/v2/copilot-grounding-spec.md`, never silently reuses
  stale cached data).

See `docs/adr/010-v2-consent-model.md`.
