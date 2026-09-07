# AVENYTH V2 — Shared Task System Spec

## Status

Draft — Phase 0 spec freeze.

## Task types

```
PERSONAL_PRIVATE
FOR_PARTNER_PROPOSED
JOINT_SHARED
AVENYTH_SUGGESTED
```

## Lifecycle

```
PROPOSED -> ACCEPTED -> ACTIVE -> COMPLETED
PROPOSED -> DECLINED
(any non-terminal state) -> ARCHIVED
```

State transitions are **server-authoritative**. The LLM/Copilot may propose a task
(`AVENYTH_SUGGESTED`) but never marks one accepted or completed.

## Type-specific rules

- `FOR_PARTNER_PROPOSED`: invisible/inactive to the recipient until they accept —
  the proposer's UI shows it as pending, the recipient must explicitly accept
  before it becomes `ACTIVE`.
- `AVENYTH_SUGGESTED`: never auto-activates. A user must `accept`, `edit`, or
  `decline` it. Every such suggestion stores provenance:
  `source_analysis_id`, `prompt_version`, `knowledge_version` — the same
  generation-metadata discipline as `specs/v2/architecture.md` §Interpretation
  Architecture.
- `JOINT_SHARED`: both members can see and update state; completion requires
  whichever confirmation flow the UI defines (out of scope here to over-specify —
  server-authoritative state machine either way).
- `PERSONAL_PRIVATE`: never visible to the other workspace member, regardless of
  workspace membership.

## Acceptance checks

- A `FOR_PARTNER_PROPOSED` task is not readable by the recipient as active work
  until accepted.
- An `AVENYTH_SUGGESTED` task never appears as `ACTIVE` without an explicit user
  action moving it there.
- `PERSONAL_PRIVATE` tasks never leak into the partner's task list (two-user IDOR
  matrix, Section 49).
