import { describe, expect, it } from "vitest";
import {
  asRelationshipAnalysisResult,
  asShadowDynamicsResult,
  asThemeStatement,
} from "@/api/analysis-content";

const statement = (over: Record<string, unknown> = {}) => ({
  text: "Ein Satz mit Provenance.",
  canonical_refs: ["metric:a:life_path"],
  knowledge_refs: ["numbers#communication"],
  workspace_evidence_refs: [],
  ...over,
});

const versionFields = {
  calculation_version: "1.0.0",
  knowledge_version: "de-v1",
  prompt_version: "1",
  model_provider: "mock",
  model_name: "mock-1",
};

const relationshipResult = {
  relationship_type: "PARTNER",
  dimensions: [
    { dimension_id: "communication", statements: [statement()] },
    { dimension_id: "closeness", statements: [statement({ canonical_refs: [], knowledge_refs: ["numbers#closeness"] })] },
  ],
  ...versionFields,
};

const shadowResult = {
  user_a_shadow_themes: [statement()],
  user_b_shadow_themes: [statement()],
  interaction_pattern: statement(),
  escalation_loop: statement(),
  deescalation_opportunities: [statement()],
  pattern_intensity: "moderate",
  recommended_micro_tasks: ["Erst zuhören, dann antworten."],
  ...versionFields,
};

describe("asThemeStatement", () => {
  it("accepts a statement whose provenance arrays are empty", () => {
    const parsed = asThemeStatement(
      statement({ canonical_refs: [], knowledge_refs: [], workspace_evidence_refs: [] }),
    );
    expect(parsed).not.toBeNull();
    expect(parsed!.canonical_refs).toEqual([]);
  });

  it("rejects a statement without text", () => {
    expect(asThemeStatement({ canonical_refs: [] })).toBeNull();
  });

  it("rejects a statement whose ref field is not a string array", () => {
    expect(asThemeStatement(statement({ knowledge_refs: [1, 2] }))).toBeNull();
  });
});

describe("asRelationshipAnalysisResult", () => {
  it("accepts a payload shaped like RelationshipAnalysisResult", () => {
    expect(asRelationshipAnalysisResult(relationshipResult)).not.toBeNull();
  });

  it("rejects null — an analysis still generating has none", () => {
    expect(asRelationshipAnalysisResult(null)).toBeNull();
  });

  it("rejects a payload with a malformed dimension", () => {
    expect(
      asRelationshipAnalysisResult({
        ...relationshipResult,
        dimensions: [{ dimension_id: "communication" }],
      }),
    ).toBeNull();
  });

  it("rejects a payload missing the version footer fields", () => {
    const { prompt_version: _p, ...withoutPrompt } = relationshipResult;
    expect(asRelationshipAnalysisResult(withoutPrompt)).toBeNull();
  });
});

describe("asShadowDynamicsResult", () => {
  it("accepts a payload with all seven result fields", () => {
    expect(asShadowDynamicsResult(shadowResult)).not.toBeNull();
  });

  it("keeps pattern_intensity as the raw string, never a number", () => {
    const parsed = asShadowDynamicsResult(shadowResult);
    expect(parsed!.pattern_intensity).toBe("moderate");
  });

  it("rejects a payload whose recommended_micro_tasks is not a string array", () => {
    expect(asShadowDynamicsResult({ ...shadowResult, recommended_micro_tasks: "nope" })).toBeNull();
  });

  it("rejects a payload whose interaction_pattern is missing", () => {
    const { interaction_pattern: _i, ...rest } = shadowResult;
    expect(asShadowDynamicsResult(rest)).toBeNull();
  });
});
