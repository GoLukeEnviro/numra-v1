# AVENYTH V2 — Relationship Type Spec

## Status

Draft — Phase 0 spec freeze. Frozen decisions: #5 (all types from V2).

## Types

```
PARTNER
DATING
FRIENDSHIP
FAMILY
SIBLINGS
PARENT_CHILD
WORK
OTHER
```

Canonical numbers (Life Path, Expression, Soul Urge, Personality, Maturity, Personal
Year/Month/Day) are identical across all types — the canon never branches on
relationship type. Only the **interpretation frame** — which knowledge entries and
which dimensions are surfaced — changes.

`PARTNER`/`DATING` are unavailable when either participant profile is a
`MANAGED_MINOR` (`specs/v2/minor-profile-policy.md`) — enforced server-side at
workspace-type-selection time, not just hidden in the UI.

## Interpretation frames (illustrative, versioned in the Knowledge Base)

```
PARTNER:
  intimacy, attachment-needs as non-diagnostic reflection, communication,
  autonomy, closeness, long-term collaboration

FRIENDSHIP:
  trust, support, boundaries, growth, communication

WORK:
  collaboration, communication, structure, autonomy, responsibility,
  power dynamics

FAMILY:
  family roles, long-term patterns, boundaries, support, expectations
```

No relationship-type frame may hard-code a phrase like "familial karma obligation"
as a system axiom — frames describe dynamics, not fate (consistent with ADR 006's
"never guess" stance and the linter's forbidden-claim patterns in
`packages/engine-interpretation`).

Relationship frames are versioned content in the Knowledge Base, the same way
`knowledge/` content is versioned for personal reports today — a frame change is a
knowledge-version bump, not a code change to the canon.

## No compatibility percentage

V2 ships **no** "87% compatible" / "82/100 relationship score" / match percentage of
any kind, consistent with ADR 006. Qualitative dimensions (the frames above,
Shadow Dynamics, Check-ins) are the only relationship output allowed until a
separate, later `relationship-score-spec.md` exists with its own formula, version,
golden fixtures, and property tests — none of which exist today.

## Acceptance checks

- All eight types are selectable when creating a `RelationshipWorkspace` between two
  adult members, except `PARTNER`/`DATING` are rejected when a `MANAGED_MINOR`
  profile is involved (structurally impossible anyway, since minors can never be
  workspace members).
- No API response or frontend surface anywhere renders a percentage or numeric score
  labeled as compatibility/match.
