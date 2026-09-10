import type { MessageKey } from "@/i18n/catalog";
import { humanizeSnakeCase } from "@/lib/analysis-status";

/**
 * The 21 relationship-frame dimension ids known at build time
 * (knowledge/relationship-frames/*.yaml, listed in the PR-WEB-05 plan). Each maps
 * to a curated `app.dynamics.dimension.<id>` label. An id outside this set (a
 * future frame) falls back to a snake_case → Title Case humanization rather than
 * rendering the raw id or dropping the dimension.
 */
export const DIMENSION_LABEL_KEYS: Record<string, MessageKey> = {
  communication: "app.dynamics.dimension.communication",
  closeness: "app.dynamics.dimension.closeness",
  autonomy: "app.dynamics.dimension.autonomy",
  needs: "app.dynamics.dimension.needs",
  strengths: "app.dynamics.dimension.strengths",
  conflict_dynamics: "app.dynamics.dimension.conflict_dynamics",
  boundaries: "app.dynamics.dimension.boundaries",
  support: "app.dynamics.dimension.support",
  pace: "app.dynamics.dimension.pace",
  collaboration: "app.dynamics.dimension.collaboration",
  structure: "app.dynamics.dimension.structure",
  responsibility: "app.dynamics.dimension.responsibility",
  power_dynamics: "app.dynamics.dimension.power_dynamics",
  family_roles: "app.dynamics.dimension.family_roles",
  long_term_patterns: "app.dynamics.dimension.long_term_patterns",
  expectations: "app.dynamics.dimension.expectations",
  loyalty: "app.dynamics.dimension.loyalty",
  shared_history: "app.dynamics.dimension.shared_history",
  rivalry_and_cooperation: "app.dynamics.dimension.rivalry_and_cooperation",
  attraction_dynamics: "app.dynamics.dimension.attraction_dynamics",
  guidance_and_independence: "app.dynamics.dimension.guidance_and_independence",
};

export function dimensionLabel(id: string, t: (key: MessageKey) => string): string {
  const key = DIMENSION_LABEL_KEYS[id];
  return key ? t(key) : humanizeSnakeCase(id);
}
