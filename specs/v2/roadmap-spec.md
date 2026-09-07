# AVENYTH V2 — Roadmap Spec

## Status

Draft — Phase 0 spec freeze.

## Types

```
14_DAY
30_DAY
QUARTER
```

## Structure

```
Roadmap
  Milestone
    Task            (specs/v2/task-system-spec.md)
  ReviewPoint
```

## Rules

The LLM may propose a Roadmap (structure, milestones, suggested tasks). It never
marks a milestone or roadmap as fulfilled — state transitions
(`accepted`/`edited`/`archived`, and milestone/task completion) are
server-authoritative, mirroring `specs/v2/task-system-spec.md`.

A Roadmap generation call stores the same generation provenance as any other LLM
output (`prompt_version`, `knowledge_version`, `model_provider`, `model_name`).

## Acceptance checks

- A generated Roadmap starts in a proposed/editable state, never pre-marked
  complete.
- Editing a Roadmap (reordering/removing milestones) does not require
  regenerating it from the LLM — edits are plain CRUD on server-authoritative
  state.
