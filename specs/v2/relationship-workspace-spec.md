# AVENYTH V2 — Relationship Workspace Spec

## Status

Draft — Phase 0 spec freeze.

## Membership

A `RelationshipWorkspace` has **exactly two active adult `User` members** in V2
Core (`WorkspaceMember` rows, `status = ACTIVE`). No group workspaces in V2 Core.
Created only through the gate in `specs/v2/connection-spec.md`.

## Sections

```
OVERVIEW
DUAL PROFILE
COMMUNICATION
CLOSENESS
AUTONOMY
NEEDS
STRENGTHS
CONFLICT DYNAMICS
SHADOW DYNAMICS
DEVELOPMENT AREAS
TIMING DYNAMICS
CHECKINS
TASKS
ROADMAPS
SHARED REFLECTION
SHARED GOALS
COPILOT
```

`DUAL PROFILE` through `TIMING DYNAMICS` render from both members' canonical
profiles + the relationship-type interpretation frame
(`specs/v2/relationship-type-spec.md`) + curated knowledge — no numeric score,
consistent with ADR 006. `SHADOW DYNAMICS` follows the dedicated pipeline in
`specs/v2/shadow-dynamics-spec.md`. `CHECKINS` follows
`specs/v2/checkin-spec.md`. `TASKS`/`ROADMAPS` follow
`specs/v2/task-system-spec.md` / `specs/v2/roadmap-spec.md`. `COPILOT` follows
`specs/v2/copilot-grounding-spec.md` (both `RELATIONSHIP_SHARED` and
`RELATIONSHIP_PRIVATE` threads render inside this tab, scoped per viewer).

## State

```
ACTIVE
DISSOLVED
```

See `specs/v2/dissolution-policy.md` for what `DISSOLVED` means for each section
(shared artifacts retained read-only, no new inference).

## Non-goals

No compatibility percentage anywhere in `OVERVIEW` or any section. No workspace
membership for a `MANAGED_MINOR`/`MANAGED_OTHER` profile. No more than two members
in V2 Core.
