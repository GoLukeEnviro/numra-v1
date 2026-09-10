/**
 * Hand-curated mock fixtures for the PR-WEB-05 Relationship / Shadow Analysis UI.
 *
 * Used by the Vitest view tests AND by e2e-system/pr-web-05-visual-baseline.spec.ts
 * (via page.route). The mock LLM provider echoes grounding raw text, so these are
 * written by hand: realistic German prose statements, plausible refs, and some
 * deliberately empty `workspace_evidence_refs` to exercise the "show empty groups"
 * rule. No claim here is a real reading — these exist only to drive the UI.
 */

import type {
  AnalysisJobOut,
  RelationshipAnalysisOut,
  ShadowDynamicsAnalysisOut,
} from "@/api/client";

const VERSIONS = {
  calculation_version: "1.0.0",
  knowledge_version: "de-rel-v1",
  prompt_version: "rel-2",
  model_provider: "mock",
  model_name: "mock-relationship-1",
} as const;

export const relationshipAnalysisResult = {
  relationship_type: "PARTNER",
  dimensions: [
    {
      dimension_id: "communication",
      statements: [
        {
          text:
            "Ihr sprecht Dinge früh an, unterscheidet euch aber im Tempo: Eine Seite will sofort klären, die andere braucht erst Zeit zum Sortieren. Benennt diesen Unterschied, dann wird aus Ungeduld kein Vorwurf.",
          canonical_refs: ["metric:a:life_path", "metric:b:expression"],
          knowledge_refs: ["relationship-frames/PARTNER#communication", "numbers#communication"],
          workspace_evidence_refs: [],
        },
      ],
    },
    {
      dimension_id: "closeness",
      statements: [
        {
          text:
            "Nähe entsteht bei euch über gemeinsame Vorhaben, nicht über lange Gespräche. Plant bewusst kleine geteilte Projekte ein, sonst driftet der Alltag auseinander.",
          canonical_refs: ["metric:a:soul_urge"],
          knowledge_refs: ["relationship-frames/PARTNER#closeness"],
          workspace_evidence_refs: ["workspace:consent:RELATIONSHIP_INSIGHTS"],
        },
      ],
    },
    {
      dimension_id: "conflict_dynamics",
      statements: [
        {
          text:
            "Im Streit zieht sich die eine Seite zurück, die andere erhöht den Druck. Vereinbart ein Signal für eine kurze Pause mit fester Wiederaufnahme, damit Rückzug nicht als Abbruch gelesen wird.",
          canonical_refs: ["metric:a:personality", "metric:b:personality"],
          knowledge_refs: ["relationship-frames/PARTNER#conflict_dynamics", "numbers#conflict_dynamics"],
          workspace_evidence_refs: [],
        },
      ],
    },
  ],
  ...VERSIONS,
} as const;

const SHADOW_VERSIONS = {
  calculation_version: "1.0.0",
  knowledge_version: "de-shadow-v1",
  prompt_version: "shadow-2",
  model_provider: "mock",
  model_name: "mock-shadow-1",
} as const;

export const shadowDynamicsResult = {
  user_a_shadow_themes: [
    {
      text:
        "Unter Druck neigt Person A dazu, Verantwortung an sich zu ziehen und dann still zu grollen, wenn die andere Seite nicht von selbst mitzieht.",
      canonical_refs: ["metric:a:life_path"],
      knowledge_refs: ["shadow-interaction/rules.yaml#overfunctioning"],
      workspace_evidence_refs: [],
    },
    {
      text:
        "Kritik wird schnell als Grundsatzurteil gehört, worauf Person A das Thema wechselt statt nachzufragen.",
      canonical_refs: ["metric:a:personality"],
      knowledge_refs: ["numbers#defensiveness"],
      workspace_evidence_refs: [],
    },
  ],
  user_b_shadow_themes: [
    {
      text:
        "Person B weicht offener Konfrontation aus und signalisiert Zustimmung, die später nicht trägt.",
      canonical_refs: ["metric:b:soul_urge"],
      knowledge_refs: ["shadow-interaction/rules.yaml#accommodation"],
      workspace_evidence_refs: [],
    },
  ],
  interaction_pattern: {
    text:
      "Je mehr Person A führt und nachfasst, desto mehr zieht sich Person B zurück — und der Rückzug lässt Person A noch stärker übernehmen.",
    canonical_refs: ["metric:a:life_path", "metric:b:soul_urge"],
    knowledge_refs: ["shadow-interaction/rules.yaml#pursue_withdraw"],
    workspace_evidence_refs: [],
  },
  escalation_loop: {
    text:
      "Ein unbeantworteter Wunsch wird zur Ansage, die Ansage zum Vorwurf, der Vorwurf zum Schweigen — und das Schweigen bestätigt beide in ihrer Sicht.",
    canonical_refs: ["metric:a:personality", "metric:b:personality"],
    knowledge_refs: ["shadow-interaction/rules.yaml#escalation"],
    workspace_evidence_refs: [],
  },
  deescalation_opportunities: [
    {
      text:
        "Der frühe Moment zählt: Ein benannter Wunsch statt einer Ansage unterbricht die Schleife, bevor sie Fahrt aufnimmt.",
      canonical_refs: ["metric:a:soul_urge"],
      knowledge_refs: ["shadow-interaction/rules.yaml#early_repair"],
      workspace_evidence_refs: [],
    },
  ],
  pattern_intensity: "moderate",
  recommended_micro_tasks: [
    "Einen offenen Wunsch als Ich-Satz formulieren, bevor er zur Forderung wird.",
    "Bei Rückzug eine feste Zeit zur Wiederaufnahme nennen.",
    "Nach Kritik einmal nachfragen, statt das Thema zu wechseln.",
  ],
  ...SHADOW_VERSIONS,
} as const;

export const relationshipAnalysisComplete: RelationshipAnalysisOut = {
  id: "rel-analysis-1",
  workspace_id: "workspace-1",
  job_id: "rel-job-1",
  status: "COMPLETE",
  relationship_type: "PARTNER",
  result: relationshipAnalysisResult as unknown as Record<string, unknown>,
  created_at: "2026-09-01T09:00:00Z",
  generated_at: "2026-09-01T09:04:00Z",
  ...VERSIONS,
};

export const shadowDynamicsComplete: ShadowDynamicsAnalysisOut = {
  id: "shadow-analysis-1",
  workspace_id: "workspace-1",
  job_id: "shadow-job-1",
  status: "COMPLETE",
  relationship_type: "PARTNER",
  result: shadowDynamicsResult as unknown as Record<string, unknown>,
  created_at: "2026-09-01T09:00:00Z",
  generated_at: "2026-09-01T09:06:00Z",
  ...SHADOW_VERSIONS,
};

export const relationshipAnalysisPending: RelationshipAnalysisOut = {
  ...relationshipAnalysisComplete,
  status: "PENDING",
  result: null,
  generated_at: null,
};

export function analysisJob(over: Partial<AnalysisJobOut> = {}): AnalysisJobOut {
  return {
    id: "rel-job-1",
    workspace_id: "workspace-1",
    analysis_type: "RELATIONSHIP_INTERPRETATION",
    status: "GENERATING",
    progress: 80,
    error_code: null,
    attempt_count: 1,
    created_at: "2026-09-01T09:00:00Z",
    updated_at: "2026-09-01T09:03:00Z",
    ...over,
  };
}
