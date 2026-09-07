# ADR 013 — Dissolution Retains Shared History, Revokes Future Access

## Status

Accepted.

## Context

Relationships end. A workspace model that either destroys all shared history on
disconnect (losing legitimate personal history, e.g. a completed roadmap or a
meaningful past shared Copilot exchange) or keeps generating new shared inferences
after a disconnect (a genuine privacy violation) are both wrong defaults.

## Decision

Disconnecting a `UserConnection` / dissolving a `RelationshipWorkspace` immediately
revokes all `ConsentGrant`s and sets the workspace to `DISSOLVED`. Everything
already generated while the workspace was active — past roadmaps, past
`RELATIONSHIP_SHARED` Copilot threads, past completed tasks, past relationship/
shadow/check-in analyses — remains **read-only** and accessible to both former
participants indefinitely (`specs/v2/dissolution-policy.md`). Nothing shared is
regenerated, re-aggregated, or used as input to a new inference after dissolution;
private source data becomes inaccessible to the other party immediately.

Account deletion follows the same spirit at the account level: the deleted user's
private content is removed, shared artifacts they participated in are retained per
the rule above but with the deleted user pseudonymized/anonymized wherever legally
and technically possible, and no orphaned PII or another user's private data is
ever left reachable as a side effect.

## Consequences

- A dissolved workspace is not a "delete everything" event — product and support
  teams should expect users to retain read access to meaningful shared history
  after a breakup/disconnect, by design.
- Every analysis/generation endpoint must check workspace state before running —
  `DISSOLVED` blocks new inference even if stale consent rows or cached context
  would otherwise make it technically possible.
- Account deletion design must be finished (pseudonymization approach validated)
  before PR-V2-10 ships; it cannot be deferred past V2 Core (Section 56 Definition
  of Done).
