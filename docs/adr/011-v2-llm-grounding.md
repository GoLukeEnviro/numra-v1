# ADR 011 — LLM Grounding Extends to Relationships, Check-ins, and Evidence

## Status

Accepted.

## Context

ADR 003 established that the LLM is never a calculator for personal numerology.
V2 adds relationship analysis, shadow dynamics, configurable check-ins, and (Phase
6) life-tracking pattern detection — all new surfaces where it would be tempting to
let the LLM "just estimate" a gap, a trend, a compatibility score, or a correlation.

## Decision

The "LLM is not a calculator" invariant extends unchanged to every V2 surface. In
addition to the existing forbidden list (Life Path, Expression, Soul Urge,
Personality, Timing, Pinnacles, Challenges, Karmic Lessons, Hidden Passion), the LLM
never computes: compatibility percentages, check-in gaps/trends/sample sizes,
correlations, statistical scores, or effect sizes
(`specs/v2/architecture.md` §Absolute invariants). All of these are deterministic or
statistical backend service output (`CheckinAnalysisService`,
`EvidencePolicy`-governed pattern analysis), handed to the LLM only as
already-computed, already-validated JSON to explain.

Every relationship/shadow/check-in/evidence statement the LLM renders is grounded
through: (1) a deterministic `StructuredContext` assembly step that the LLM never
performs itself, and (2) a `basis_type` classification
(`NUMEROLOGY_MODEL` / `OBSERVED_WORKSPACE_DATA` / `MIXED` /
`INSUFFICIENT_EVIDENCE`) attached to the output (`specs/v2/copilot-grounding-spec.md`).
No compatibility percentage ships anywhere until a separately specced, versioned,
golden-fixture-backed `relationship-score-spec.md` exists — none does today
(`specs/v2/relationship-type-spec.md`).

An explicit `ContextBuilder` replaces ad hoc prompt assembly for every Copilot
surface, and all user-authored content (journal, chat, reflections) is treated as
`UNTRUSTED_USER_DATA`, structurally separated from `SYSTEM_POLICY` in the prompt.

## Consequences

- Any PR introducing a new LLM-facing surface must show where its numeric/
  statistical inputs come from (a named deterministic service) and what
  `basis_type` its output carries — reviewers can reject a PR that lets the LLM
  "just estimate" a number.
- Prompt-injection and LLM-leakage tests are mandatory CI additions for every new
  Copilot/analysis surface (Section 48).
- `INSUFFICIENT_EVIDENCE` must be a reachable, correctly rendered state in every
  such surface, not merely a theoretical enum value.
