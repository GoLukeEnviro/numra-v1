# AVENYTH V2 — Privacy Spec

## Status

Draft — Phase 0 spec freeze.

## Cross-cutting privacy boundaries

This spec indexes the privacy guarantees defined in detail elsewhere so they can be
tested and audited as one matrix:

| Boundary | Defined in |
|---|---|
| Consent scopes, default grants, revocation | `specs/v2/consent-spec.md` |
| Raw check-in answers stay submitter-only | `specs/v2/checkin-spec.md` |
| Private Copilot threads never leak to the partner | `specs/v2/copilot-grounding-spec.md` |
| Private tasks never leak to the partner | `specs/v2/task-system-spec.md` |
| Private reflections require explicit `SHARE` action | `specs/v2/task-system-spec.md` (Shared Reflection) |
| Managed minor profiles never become connectable accounts | `specs/v2/minor-profile-policy.md` |
| Legacy V1 relationships stay single-owner | `specs/v2/connection-spec.md` |
| Dissolved workspaces: read-only retained artifacts, no new inference | `specs/v2/dissolution-policy.md` |

## Two-user authorization matrix (Section 49)

Mandatory test suite: create two real users, `USER_A` and `USER_B`. Verify `A`
cannot access, and is not exposed to via any endpoint or Copilot context:

```
B's private profile data
B's private notes
B's private tasks
B's private reflection
B's private Copilot
B's other workspaces
B's raw check-in response
B's managed minor private profile
```

unless an explicit, currently-active consent/share mechanism grants it. Verify the
same in the other direction (`B` cannot access `A`'s equivalents). This matrix is
re-run for every new V2 surface before it is considered done (Section 56).

## Analytics/observability boundary

Metrics (`specs/v2/api-contract.md` §Observability) never log: journal contents,
chat text, private notes, or raw birth profile content. Only counters/timings on
event *occurrence* are recorded.

## Account deletion

See `specs/v2/dissolution-policy.md` §Delete Account for the full PII-removal and
shared-artifact-anonymization rules.
