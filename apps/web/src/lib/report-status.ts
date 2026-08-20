import type { ReportJobStatus, ReportType } from "@/api/client";

/**
 * Presentation metadata for the report generation job state machine
 * (apps/api/src/numra_api/models/enums.py::ReportJobStatus).
 *
 * Deliberately a pure lookup with no derived progress maths: the job's own
 * `progress` field is the only progress number ever shown, and it is rendered
 * verbatim. A job can move *backwards* through these states when the queue
 * retries with backoff (GENERATING → QUEUED → OUTLINE …), so nothing here may
 * assume the sequence is monotonic or infer a percentage from the status alone.
 */

export type JobTone = "pending" | "working" | "done" | "failed";

export interface JobStatusPresentation {
  label: string;
  /** One short sentence describing what the backend is doing in this state. */
  description: string;
  tone: JobTone;
  /** True when the job will not change state again on its own — stop polling. */
  terminal: boolean;
}

const JOB_STATUS: Record<ReportJobStatus, JobStatusPresentation> = {
  QUEUED: {
    label: "Queued",
    description: "Waiting for a generation worker to pick this report up.",
    tone: "pending",
    terminal: false,
  },
  OUTLINE: {
    label: "Outlining",
    description: "Planning the section structure of the report.",
    tone: "working",
    terminal: false,
  },
  GENERATING: {
    label: "Writing",
    description: "Writing each section from the verified calculation.",
    tone: "working",
    terminal: false,
  },
  VALIDATING: {
    label: "Validating",
    description: "Checking every numeric claim against the canonical profile.",
    tone: "working",
    terminal: false,
  },
  ASSEMBLING: {
    label: "Assembling",
    description: "Putting the validated sections together.",
    tone: "working",
    terminal: false,
  },
  COMPLETE: {
    label: "Complete",
    description: "The report is ready to read.",
    tone: "done",
    terminal: true,
  },
  FAILED: {
    label: "Failed",
    description: "Generation stopped before a complete report could be produced.",
    tone: "failed",
    terminal: true,
  },
  CANCELLED: {
    label: "Cancelled",
    description: "This generation run was cancelled.",
    tone: "failed",
    terminal: true,
  },
};

/**
 * Unknown statuses are possible if the backend enum grows ahead of this client, so
 * this never throws — it falls back to a neutral, non-terminal "working" state and
 * shows the raw status string rather than inventing a friendlier one.
 */
export function describeJobStatus(status: string): JobStatusPresentation {
  const known = JOB_STATUS[status as ReportJobStatus];
  if (known) return known;
  return {
    label: status,
    description: "Generation is in progress.",
    tone: "working",
    terminal: false,
  };
}

export function isJobTerminal(status: string): boolean {
  return describeJobStatus(status).terminal;
}

/**
 * Clamps the job's own progress into 0-100 for a progress bar's width. This does
 * not invent progress: an out-of-range value is only bounded, never replaced by an
 * estimate, and callers still render `progress` itself as the displayed number.
 */
export function progressPercent(progress: number): number {
  if (!Number.isFinite(progress)) return 0;
  return Math.min(100, Math.max(0, progress));
}

export interface ReportTypeOption {
  value: Extract<ReportType, "QUICK" | "FULL" | "ULTIMATE">;
  label: string;
  description: string;
}

/**
 * The report types offered in the UI.
 *
 * `CUSTOM` is intentionally absent: it requires a `custom_total_target_words` value
 * that `POST /v1/reports` does not currently accept, so offering it would produce a
 * guaranteed server error.
 */
export const REPORT_TYPE_OPTIONS: readonly ReportTypeOption[] = [
  {
    value: "QUICK",
    label: "Quick",
    description: "A short orientation across the core numbers.",
  },
  {
    value: "FULL",
    label: "Full",
    description: "The complete reading, section by section.",
  },
  {
    value: "ULTIMATE",
    label: "Ultimate",
    description: "The longest form, with cycles and timing worked through in depth.",
  },
] as const;

export function describeReportType(reportType: string): string {
  return REPORT_TYPE_OPTIONS.find((o) => o.value === reportType)?.label ?? reportType;
}
