"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  api,
  ApiError,
  type AnalysisJobOut,
  type RelationshipAnalysisOut,
  type ShadowDynamicsAnalysisOut,
} from "@/api/client";
import { isAnalysisJobTerminal } from "@/lib/analysis-status";
import { isPhaseDisabledError } from "@/components/ui/states";

export const ANALYSIS_POLL_INTERVAL_MS = 2500;

/** A single failed poll is usually a blip (a redeploy, a rate-limit tick) and must
 *  not tear down a generation the user is watching. */
const MAX_CONSECUTIVE_POLL_FAILURES = 4;

/** The initial "is there already an analysis?" load gets the same transient-blip
 *  tolerance as polling — except a 404 (no analysis yet) and a phase gate, which
 *  are answers, not failures. */
const INITIAL_LOAD_MAX_ATTEMPTS = 3;
const INITIAL_LOAD_RETRY_DELAY_MS = 500;

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function newIdempotencyKey(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  return `analysis-${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

export type AnalysisKind = "relationship" | "shadow";
export type AnalysisOut = RelationshipAnalysisOut | ShadowDynamicsAnalysisOut;

export type AnalysisProgress =
  | { phase: "loading" }
  /** No analysis has ever been generated for this workspace/kind (GET latest → 404). */
  | { phase: "empty" }
  /** GET latest or the launch POST returned a phase-gated code (e.g. CONSENT_NOT_GRANTED). */
  | { phase: "phaseDisabled"; error: ApiError }
  | { phase: "error"; error: unknown }
  /** Generation is running — `job` is null only until the first poll lands. */
  | { phase: "pending"; analysis: AnalysisOut | null; job: AnalysisJobOut | null }
  | { phase: "failed"; analysis: AnalysisOut | null; job: AnalysisJobOut | null }
  | { phase: "complete"; analysis: AnalysisOut };

export interface UseAnalysisProgress {
  reload: () => void;
  /** Start a generation (POST). No-op while one is already running. */
  launch: () => void;
  launching: boolean;
}

/**
 * Owns one analysis section's lifecycle: the initial "latest COMPLETE?" load, the
 * launch POST with a per-attempt `Idempotency-Key`, and job polling until a terminal
 * job status, at which point the full body is re-read via GET `.../{analysis_id}`.
 *
 * Adapted 1:1 from lib/use-report-progress.ts, including its effect-local `cancelled`
 * flag: all of `start`/`poll`/`runLaunch` live inside the effect so each effect run
 * (mount, workspace/kind change, `reload()`) is fully isolated — a stale promise
 * from a previous run can never clear the current run's timer. `launch()` is exposed
 * through a ref the effect swaps each run and clears on cleanup.
 *
 * Same deliberate properties as the report hook: the job's `progress` is never
 * smoothed or assumed monotonic, and the analysis row is re-fetched once the job
 * reports COMPLETE because the job row and the analysis row are separate.
 */
export function useAnalysisProgress(
  workspaceId: string,
  kind: AnalysisKind,
): AnalysisProgress & UseAnalysisProgress {
  const [progress, setProgress] = useState<AnalysisProgress>({ phase: "loading" });
  const [launching, setLaunching] = useState(false);
  const [reloadTick, setReloadTick] = useState(0);

  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  /** Survives effect re-runs on purpose: a POST whose response was lost may have
   *  created the job server-side, so the next launch must re-send the SAME key to
   *  re-hit that job instead of queueing a duplicate (see runLaunch's catch). */
  const idempotencyKeyRef = useRef<string | null>(null);
  const launchRef = useRef<() => void>(() => {});

  const reload = useCallback(() => setReloadTick((t) => t + 1), []);
  const launch = useCallback(() => launchRef.current(), []);

  useEffect(() => {
    let cancelled = false;
    let failureCount = 0;
    let launchInFlight = false;

    function clearTimer() {
      if (timerRef.current !== null) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
    }

    const getLatest = (): Promise<AnalysisOut> =>
      kind === "relationship"
        ? api.workspaces.relationshipAnalysis.getLatest(workspaceId)
        : api.workspaces.shadowDynamics.getLatest(workspaceId);

    const getById = (analysisId: string): Promise<AnalysisOut> =>
      kind === "relationship"
        ? api.workspaces.relationshipAnalysis.get(workspaceId, analysisId)
        : api.workspaces.shadowDynamics.get(workspaceId, analysisId);

    const create = (idempotencyKey: string): Promise<AnalysisOut> =>
      kind === "relationship"
        ? api.workspaces.relationshipAnalysis.create(workspaceId, idempotencyKey)
        : api.workspaces.shadowDynamics.create(workspaceId, idempotencyKey);

    async function poll(analysis: AnalysisOut) {
      let job: AnalysisJobOut;
      try {
        job = await api.analysisJobs.get(analysis.job_id);
        failureCount = 0;
      } catch (error) {
        failureCount += 1;
        if (failureCount >= MAX_CONSECUTIVE_POLL_FAILURES && !cancelled) {
          clearTimer();
          setProgress({ phase: "error", error });
        }
        return;
      }
      if (cancelled) return;

      if (!isAnalysisJobTerminal(job.status)) {
        setProgress({ phase: "pending", analysis, job });
        return;
      }

      clearTimer();
      try {
        const fresh = await getById(analysis.id);
        if (cancelled) return;
        setProgress(
          job.status === "COMPLETE"
            ? { phase: "complete", analysis: fresh }
            : { phase: "failed", analysis: fresh, job },
        );
      } catch (error) {
        if (!cancelled) setProgress({ phase: "error", error });
      }
    }

    function startPolling(analysis: AnalysisOut) {
      clearTimer();
      failureCount = 0;
      void poll(analysis);
      timerRef.current = setInterval(() => void poll(analysis), ANALYSIS_POLL_INTERVAL_MS);
    }

    async function start() {
      setProgress({ phase: "loading" });
      let latest: AnalysisOut | undefined;
      let lastError: unknown;
      for (let attempt = 1; attempt <= INITIAL_LOAD_MAX_ATTEMPTS && !cancelled; attempt += 1) {
        try {
          latest = await getLatest();
          break;
        } catch (error) {
          if (error instanceof ApiError && error.status === 404) {
            if (!cancelled) setProgress({ phase: "empty" });
            return;
          }
          if (isPhaseDisabledError(error)) {
            if (!cancelled) setProgress({ phase: "phaseDisabled", error });
            return;
          }
          lastError = error;
          if (attempt < INITIAL_LOAD_MAX_ATTEMPTS) await delay(INITIAL_LOAD_RETRY_DELAY_MS);
        }
      }
      if (cancelled) return;
      if (latest === undefined) {
        setProgress({ phase: "error", error: lastError });
        return;
      }

      if (latest.status === "COMPLETE" || latest.result !== null) {
        setProgress({ phase: "complete", analysis: latest });
        return;
      }
      // Defensive (design decision #6): a non-terminal `latest` — including a job
      // whose creating POST lost its response — resumes polling instead of stalling.
      setProgress({ phase: "pending", analysis: latest, job: null });
      startPolling(latest);
    }

    function runLaunch() {
      if (launchInFlight || timerRef.current !== null) return;
      launchInFlight = true;
      setLaunching(true);
      const key = idempotencyKeyRef.current ?? newIdempotencyKey();
      idempotencyKeyRef.current = key;

      void (async () => {
        try {
          const analysis = await create(key);
          idempotencyKeyRef.current = null; // attempt landed — next launch is a new attempt
          if (cancelled) return;
          setProgress({ phase: "pending", analysis, job: null });
          startPolling(analysis);
        } catch (error) {
          // Only a phase gate (relationship type / consent) invalidates the key: it
          // needs a genuinely new attempt once the precondition is fixed. A network
          // or 5xx error may have created the job while losing the response, so the
          // key is KEPT — the next click re-sends it and re-hits that same job
          // (backend idempotency) rather than queueing a duplicate.
          if (isPhaseDisabledError(error)) idempotencyKeyRef.current = null;
          if (cancelled) return;
          setProgress(
            isPhaseDisabledError(error)
              ? { phase: "phaseDisabled", error }
              : { phase: "error", error },
          );
        } finally {
          launchInFlight = false;
          if (!cancelled) setLaunching(false);
        }
      })();
    }

    launchRef.current = runLaunch;
    void start();

    return () => {
      cancelled = true;
      clearTimer();
      launchRef.current = () => {};
    };
  }, [workspaceId, kind, reloadTick]);

  return { ...progress, reload, launch, launching };
}
