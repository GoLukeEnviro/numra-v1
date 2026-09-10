import type { AnalysisJobStatus } from "@/api/client";

/**
 * Presentation metadata for the relationship/shadow analysis job state machine
 * (apps/api/.../models::AnalysisJobStatus). Same philosophy as lib/report-status.ts:
 * a pure lookup, hardcoded English (its own test pins the strings), no derived
 * progress maths — the job's own `progress` field is the only number ever shown and
 * it is rendered verbatim. A job can move backwards (GENERATING → QUEUED) on a
 * queue retry, so nothing here assumes the sequence is monotonic.
 */

export type AnalysisJobTone = "pending" | "working" | "done" | "failed";

export interface AnalysisJobStatusPresentation {
  label: string;
  description: string;
  tone: AnalysisJobTone;
  /** True when the job will not change state again on its own — stop polling. */
  terminal: boolean;
}

const JOB_STATUS: Record<AnalysisJobStatus, AnalysisJobStatusPresentation> = {
  QUEUED: {
    label: "Queued",
    description: "Waiting for a worker to pick this analysis up.",
    tone: "pending",
    terminal: false,
  },
  GENERATING: {
    label: "Generating",
    description: "Working through each dimension from the verified profiles.",
    tone: "working",
    terminal: false,
  },
  VALIDATING: {
    label: "Validating",
    description: "Checking every statement against its cited sources.",
    tone: "working",
    terminal: false,
  },
  COMPLETE: {
    label: "Complete",
    description: "The analysis is ready to read.",
    tone: "done",
    terminal: true,
  },
  FAILED: {
    label: "Failed",
    description: "Generation stopped before a complete analysis could be produced.",
    tone: "failed",
    terminal: true,
  },
};

/**
 * Unknown statuses are possible if the backend enum grows ahead of this client, so
 * this never throws — it falls back to a neutral, non-terminal "working" state and
 * shows the raw status string rather than inventing a friendlier one.
 */
export function describeAnalysisJobStatus(status: string): AnalysisJobStatusPresentation {
  const known = JOB_STATUS[status as AnalysisJobStatus];
  if (known) return known;
  return {
    label: status,
    description: "Generation is in progress.",
    tone: "working",
    terminal: false,
  };
}

export function isAnalysisJobTerminal(status: string): boolean {
  return describeAnalysisJobStatus(status).terminal;
}

/**
 * Coarse `pattern_intensity` label (e.g. "low"/"moderate"/"high"). Rendered ONLY as
 * text — never a number, bar, percentage or `role="progressbar"`. Unknown values are
 * humanized rather than dropped.
 */
export function humanizeSnakeCase(value: string): string {
  return value
    .split(/[_\s]+/)
    .filter((part) => part.length > 0)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}
