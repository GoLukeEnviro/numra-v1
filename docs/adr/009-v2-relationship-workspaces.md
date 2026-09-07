# ADR 009 — Relationship Workspaces: Two Real Adult Accounts, No Directory

## Status

Accepted.

## Context

V1's `RelationshipComparison` compares two calculations owned by a single user —
there was never a second, independent account involved, and therefore no mutual
consent. AVENYTH V2 needs genuine two-person shared spaces (Dual Profile, Shadow
Dynamics, Check-ins, Tasks, Roadmaps, Shared Reflection, Copilot) without turning
into a social/dating discovery product, which is explicitly out of scope
(`specs/v2/product-vision.md`).

## Decision

A `RelationshipWorkspace` connects **exactly two active adult `User` accounts**,
created only after a real `ConnectionInvitation` (`INVITE_LINK` / `INVITE_CODE` /
`EMAIL`) is accepted and consent is configured (`specs/v2/connection-spec.md`,
`specs/v2/consent-spec.md`). There is no public people directory and no username
search in V2 Core — the only path into a workspace is an explicit invitation.

All eight relationship types (`specs/v2/relationship-type-spec.md`) are supported
from V2's first release rather than gating types behind later phases — the canon
values never change per type, only the interpretation frame does, so there is no
technical reason to stage type rollout.

Legacy V1 `RelationshipComparison` rows are never auto-converted into
`RelationshipWorkspace`s — they lack the mutual-consent step V2 requires. They stay
read-only-visible to their original owner; a real workspace requires a real new
connection.

## Consequences

- No group workspaces in V2 Core — a third member requires a future, separately
  designed extension.
- A `MANAGED_MINOR`/`MANAGED_OTHER` profile can never be a `WorkspaceMember`
  (ADR 012); this is enforced at the same gate as the two-adult-accounts rule.
- Product growth into any form of discovery/matching is a distinct future decision,
  not an incremental extension of this workspace model.
