# AVENYTH V2 — Dissolution & Account Deletion Policy

## Status

Frozen product decision (#11 in the decision log): after disconnect, shared
historical artifacts stay read-only accessible to both former participants.

## Disconnect

Disconnecting a `UserConnection` / dissolving a `RelationshipWorkspace`:

- Future data access ends **immediately**.
- All `ConsentGrant`s between the two members are revoked.
- `RelationshipWorkspace.status` → `DISSOLVED`.

## What is retained read-only

```
past roadmap
past shared Copilot thread (RELATIONSHIP_SHARED only)
past completed task
past relationship analysis (Dual Profile, Shadow Dynamics, Check-in analyses
  already generated)
```

Both former participants keep read access to these. Never regenerated, never
re-aggregated, never used as input to a new inference.

## What is disabled at dissolution

```
Shared artifacts:                 RETAIN_READ_ONLY
Private source data:              REVOKE_ACCESS (to the other party — the owner
                                   keeps their own data regardless)
Future shared operations:         DISABLED
Consent:                          REVOKED
Chat:                             read-only
Tasks:                            archived or read-only
Roadmaps:                         read-only
Check-ins:                        historic shared derived results retained;
                                   raw private answers remain with the original
                                   submitter only, as always
```

No regeneration. No new inference. No new data aggregation. No new private-source
retrieval — a dissolved workspace's Copilot cannot fetch fresh context, even from
data that was previously consented, because the consent itself is revoked.

## Delete account

Deleting a `User` account must define, before shipping:

- **Private content deletion** — the account's own private notes, tasks,
  reflections, Copilot threads, Managed Profiles they solely own.
- **Shared artifact handling** — where a shared artifact is retained (per
  Disconnect rules above) but one participant is gone, the deleted user is
  pseudonymized/anonymized in that artifact wherever legally and technically
  possible, rather than leaving a dangling reference or exposing residual PII.
- **Remaining participant access** — the surviving participant keeps read access to
  the anonymized shared artifact, consistent with the Disconnect rules.
- **Audit handling** — `AdminAuditEvent` entries referencing the deleted user follow
  the existing admin-audit retention rules; they are not silently purged, but they
  must not become a PII leak vector post-deletion.
- **PII removal** — no orphaned PII. No other user's private source data is ever
  left behind as a side effect of one account's deletion.

## Acceptance checks (Section 50 / 51 relevant excerpts)

- After A/B disconnect: workspace is `DISSOLVED`, no new inference is possible, and
  private source access from one party to the other is gone, while previously
  generated shared artifacts remain readable by both.
- Deleting an account never leaves the other former participant unable to read
  artifacts the policy says should be retained, and never leaves the deleted user's
  private data reachable by anyone else.

See `docs/adr/013-v2-workspace-dissolution.md`.
