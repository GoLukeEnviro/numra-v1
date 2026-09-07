# AVENYTH V2 — Check-in Spec

## Status

Frozen product decision (#8 in the decision log) — deviates from the recommended
default of a fixed five-dimension set. Check-in dimensions are **configurable**,
not hardcoded.

## Template model

```
CheckinTemplate
  id, workspace_id, version, created_at, active

CheckinDimension
  id, workspace_id, semantic_key, label, description,
  scale_min, scale_max, sort_order, active,
  created_at, retired_at (nullable)
```

Each `RelationshipWorkspace` gets its own `CheckinTemplate`, versioned. The default
template (version 1) ships with:

```
closeness
communication
understanding
autonomy
conflict_load
```

Scale: `1..10` for every dimension unless a dimension defines otherwise.

## Configuration rules

- Users may activate/deactivate a dimension, add a custom dimension, or change a
  dimension's `label`/`description`.
- A dimension's `semantic_key`, once used in any submitted `CheckinResponse`, is
  **never redefined retroactively** — changing its meaning requires retiring it
  (`retired_at`) and introducing a new `semantic_key`.
- Every historical response stays bound to the `checkin_template_version` active
  when it was submitted. Aggregation/trend logic must group by
  `(semantic_key, checkin_template_version)`, never blindly average across template
  versions with different meanings.
- Example additional dimensions: `trust`, `emotional_safety`, `quality_time`,
  `support`, `sexual_connection`.
- `sexual_connection` (and any dimension of that class) is **never available** in
  `PARENT_CHILD`, `SIBLINGS`, `WORK` relationship types, or in any workspace/context
  involving a managed minor profile — enforced server-side at dimension-activation
  time, not just hidden in the UI.

## Privacy (Section 19 — frozen)

Each participant submits separately. Raw answers are `SUBMITTER_ONLY` — a partner
can never read the other's raw numeric answers, at any point, through any endpoint.

Only after **both** participants have submitted for a given check-in cycle does
`CheckinAnalysisService` compute the shared derived result. Partners see only the
derived shared analysis, never raw values.

## Deterministic analysis (Section 20)

The LLM computes **none** of: gap, trend, mean, delta, sample size. A backend
service computes:

```
absolute_gap
direction
rolling_trend
sample_size
historical_delta
sufficient_evidence
```

as a `CheckinAnalysis` JSON document. The LLM only explains that already-computed
JSON — never recomputes or overrides it (same invariant as
`specs/v2/evidence-policy.md`).

## Acceptance checks

- A dimension's `semantic_key` is provably immutable once any response references
  it (migration/constraint-level, not just app-level convention).
- Neither participant's API responses ever include the other's raw
  `CheckinResponse` values, under any scope or role.
- `CheckinAnalysis` is only computable after both participants have submitted for
  the cycle; a request before that returns "awaiting partner", never partial raw
  data.
- Trend calculations correctly segment by `checkin_template_version` when a
  workspace has evolved its template over time.
