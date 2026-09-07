# ADR 012 — Minors Get Managed Profiles, Never Accounts

## Status

Accepted — deviates from the initially recommended default of scoped minor
accounts (frozen decision #4 in the V2 decision log).

## Context

AVENYTH's relationship features (Connections, shared Copilot, Check-ins) are only
meaningful and safe between consenting adults. The product still wants to support
family/parent-child numerological analysis, which requires a minor's birth data to
exist somewhere in the system.

## Decision

AVENYTH accounts are 18+ only. A minor exists only as a `MANAGED_MINOR` `Person`
profile owned by an adult `User` account — no login, no session, no private
Copilot identity of their own, no public discovery, no `ConnectionInvitation`
target, no `WorkspaceMember` role, no `PARTNER`/`DATING` relationship type, no
public profile, no direct messages (`specs/v2/minor-profile-policy.md`).

Minor status is derived at read time from `birth_date` + the current date — never
a persisted, potentially-stale boolean. `PARENT_CHILD`/`FAMILY`/`SIBLINGS` analyses
are permitted between an adult's own `SELF` profile and their owned managed
profile, as a private, single-account analysis — never a shared workspace.

Multiple guardians sharing visibility into one managed profile requires a future,
explicit `ManagedProfileSharing` mechanism — never implicit. A managed minor
profile reaching majority is not auto-converted into a real account; that would
require a separate, later claim/transfer spec.

## Consequences

- Every V2 workspace/connection/copilot code path must reject a `MANAGED_MINOR`
  profile as a participant at the API layer, not merely hide the option in the UI —
  this is part of the Section 55 no-go list.
- Product growth toward guardian co-access or minor-to-adult account transfer are
  explicitly deferred, separately specced features, not implicit extensions.
- The two-user IDOR matrix and the dedicated minor-profile E2E journey
  (`specs/v2/minor-profile-policy.md` §Acceptance checks) are required tests before
  any release that touches Connections or Workspaces.
