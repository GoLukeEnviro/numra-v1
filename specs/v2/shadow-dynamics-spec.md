# AVENYTH V2 — Shadow Dynamics Spec

## Status

Draft — Phase 0 spec freeze.

## Principle

The LLM never invents shadow themes. Every theme statement must carry provenance
back to canon values, curated knowledge, or workspace evidence.

## Pipeline

```
CanonicalProfile A
+
CanonicalProfile B
+
RelationshipType
+
Curated Shadow Knowledge
+
Relationship rules
+
allowed evidence (per consent, specs/v2/consent-spec.md)
      |
StructuredShadowContext   (deterministic assembly, no LLM)
      |
LLM Renderer
      |
ShadowDynamicsResult
```

Assembly of `StructuredShadowContext` is deterministic backend code — it selects
which knowledge entries and which consented evidence rows are eligible, and hands
the LLM a closed context. The LLM's job is limited to rendering/explaining that
context in natural language.

## `ShadowDynamicsResult` shape

```
user_a_shadow_themes
user_b_shadow_themes
interaction_pattern
escalation_loop
deescalation_opportunities
pattern_intensity
recommended_micro_tasks
```

Every theme-level statement carries a provenance record: `canonical_refs`,
`knowledge_refs`, and `workspace_evidence_refs` (empty array if none used — never
omitted).

## Forbidden output

No psychiatric diagnosis. No personality-disorder language. No attachment style
framed as a diagnosis (it may appear only as a descriptive, non-diagnostic
reflection, matching the `PARTNER` frame's "attachment-needs as non-diagnostic
reflection" language in `specs/v2/relationship-type-spec.md`). These are enforced
the same way the existing report linter enforces forbidden claim patterns
(`packages/engine-interpretation` `report/linter.py`) — extend the same
linting/validation layer for Shadow Dynamics output rather than inventing a
parallel mechanism.

## Consent gating

`StructuredShadowContext` assembly must check `PRIVATE_JOURNAL`/`OTHER_RELATIONSHIPS`
etc. consent scopes before including any evidence beyond `CORE_NUMEROLOGY` /
`RELATIONSHIP_INSIGHTS`. Revoking a scope mid-session invalidates future Shadow
Dynamics regeneration using that scope, per `specs/v2/consent-spec.md`.

## Acceptance checks

- Every theme in a generated `ShadowDynamicsResult` has a non-empty provenance
  category (canonical or knowledge, at minimum).
- Linter/validator rejects any generated result containing diagnostic-sounding
  language before it is persisted or shown.
- Regenerating after a relevant consent revoke either falls back to
  `INSUFFICIENT_EVIDENCE` framing (`specs/v2/copilot-grounding-spec.md`) or excludes
  the revoked evidence class entirely — never silently reuses it.
