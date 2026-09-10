/**
 * Frontend-side type model for `RelationshipAnalysisOut.result` /
 * `ShadowDynamicsAnalysisOut.result`.
 *
 * The generated OpenAPI schema types `result` as `{ [key: string]: unknown } | null`
 * because the backend stores it as an open JSON column. The real shape is pinned by
 * `RelationshipAnalysisResult` / `ShadowDynamicsResult` / `ThemeStatement` in
 * packages/engine-relationship-interpretation/src/numra_relationship_interpretation/
 * schemas.py — this module mirrors that contract exactly.
 *
 * Like api/report-content.ts this is a type + shallow structural guard, never a
 * re-implementation: nothing here derives, reformats or infers a value. A payload
 * that does not match produces an error state rather than a partial render.
 */

export interface ThemeStatement {
  text: string;
  /** Provenance. `canonical_refs`/`knowledge_refs` are never both empty (backend
   *  linter), `workspace_evidence_refs` is always present (empty tuple if unused).
   *  Optional here only to tolerate a pre-field payload — the views render every
   *  group, empty ones included. */
  canonical_refs?: string[];
  knowledge_refs?: string[];
  workspace_evidence_refs?: string[];
}

export interface DimensionThemes {
  dimension_id: string;
  statements: ThemeStatement[];
}

interface AnalysisVersionFields {
  calculation_version: string;
  knowledge_version: string;
  prompt_version: string;
  model_provider: string;
  model_name: string;
}

export interface RelationshipAnalysisResult extends AnalysisVersionFields {
  relationship_type: string;
  dimensions: DimensionThemes[];
}

export interface ShadowDynamicsResult extends AnalysisVersionFields {
  user_a_shadow_themes: ThemeStatement[];
  user_b_shadow_themes: ThemeStatement[];
  interaction_pattern: ThemeStatement;
  escalation_loop: ThemeStatement;
  deescalation_opportunities: ThemeStatement[];
  /** Coarse, non-numeric severity label — rendered as text only. */
  pattern_intensity: string;
  /** Deterministically derived from the pattern; plain strings, no provenance. */
  recommended_micro_tasks: string[];
}

function isStringArray(value: unknown): value is string[] {
  return Array.isArray(value) && value.every((entry) => typeof entry === "string");
}

/** An absent ref array is tolerated; a present one must be `string[]`. */
function refsOk(value: unknown): boolean {
  return value === undefined || isStringArray(value);
}

export function asThemeStatement(value: unknown): ThemeStatement | null {
  if (typeof value !== "object" || value === null) return null;
  const v = value as Record<string, unknown>;
  if (typeof v.text !== "string") return null;
  if (!refsOk(v.canonical_refs) || !refsOk(v.knowledge_refs) || !refsOk(v.workspace_evidence_refs)) {
    return null;
  }
  return value as unknown as ThemeStatement;
}

function isDimension(value: unknown): value is DimensionThemes {
  if (typeof value !== "object" || value === null) return false;
  const v = value as Record<string, unknown>;
  if (typeof v.dimension_id !== "string") return false;
  if (!Array.isArray(v.statements)) return false;
  return v.statements.every((s) => asThemeStatement(s) !== null);
}

function hasVersionFields(v: Record<string, unknown>): boolean {
  return (
    typeof v.calculation_version === "string" &&
    typeof v.knowledge_version === "string" &&
    typeof v.prompt_version === "string" &&
    typeof v.model_provider === "string" &&
    typeof v.model_name === "string"
  );
}

export function asRelationshipAnalysisResult(value: unknown): RelationshipAnalysisResult | null {
  if (typeof value !== "object" || value === null) return null;
  const v = value as Record<string, unknown>;
  if (typeof v.relationship_type !== "string") return null;
  if (!Array.isArray(v.dimensions) || !v.dimensions.every(isDimension)) return null;
  if (!hasVersionFields(v)) return null;
  return value as unknown as RelationshipAnalysisResult;
}

export function asShadowDynamicsResult(value: unknown): ShadowDynamicsResult | null {
  if (typeof value !== "object" || value === null) return null;
  const v = value as Record<string, unknown>;
  const themeArrays = [v.user_a_shadow_themes, v.user_b_shadow_themes, v.deescalation_opportunities];
  if (!themeArrays.every((arr) => Array.isArray(arr) && arr.every((s) => asThemeStatement(s) !== null))) {
    return null;
  }
  if (asThemeStatement(v.interaction_pattern) === null) return null;
  if (asThemeStatement(v.escalation_loop) === null) return null;
  if (typeof v.pattern_intensity !== "string") return null;
  if (!isStringArray(v.recommended_micro_tasks)) return null;
  if (!hasVersionFields(v)) return null;
  return value as unknown as ShadowDynamicsResult;
}
