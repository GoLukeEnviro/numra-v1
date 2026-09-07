# AVENYTH V2 — Evidence Policy

## Status

Draft — Phase 0 spec freeze. Phase 6 scope (Section 15, #15 in the decision log):
Life Tracking / Evidence ships only after Relationship Core is done.

## Principle

Statistical/correlational statements require deterministic, versioned rules — never
an ad hoc threshold chosen at generation time, and never computed by the LLM.

## `EvidencePolicy` (versioned)

```
minimum_total_sample_count
minimum_sample_count_per_bucket
minimum_observation_window
missing_data_handling
outlier_policy
multiple_comparison_protection
effect_size_threshold
confidence_category
```

Every threshold must have a documented rationale in the policy's changelog — no
"magic number" without justification. `NO_RELIABLE_PATTERN` is a valid and expected
output, not an error state.

## Life Tracking data model

```
metrics: mood, energy, sleep, stress, focus, custom metric
```

A daily entry stores `person_id`, `date`, `calculation_id` (the `Calculation`
snapshot active at entry time, for traceability), and metric values. It never
stores a new Personal Day/Month/Year value — those are always derived from the
canon at read time, never persisted as a second source of truth.

## Correlation language

Never causal:

> "Personal Day 5 verursacht höhere Energie." — forbidden.

Allowed, with mandatory qualifiers:

> "An den bislang beobachteten Personal-Day-5-Tagen lag deine gemessene Energie im
> Mittel höher als deine persönliche Baseline."

Every such statement must display, alongside the claim: sample size, observation
period, and uncertainty/confidence category. This is enforced the same way as the
report linter's forbidden-claim patterns — a dedicated validator rejects any
correlation statement missing these three qualifiers before it is shown.

## Relationship to `basis_type`

Evidence-Layer statements use `OBSERVED_WORKSPACE_DATA` or `MIXED` classification
per `specs/v2/copilot-grounding-spec.md` — never `NUMEROLOGY_MODEL` alone, since
they are, by definition, based on tracked data.

## Acceptance checks

- No correlation statement in the product ships without sample size, observation
  window, and confidence category attached.
- `NO_RELIABLE_PATTERN` is reachable and correctly rendered when the policy's
  minimums are not met.
- Life Tracking entries never overwrite or shadow the canon's Personal
  Day/Month/Year computation.
