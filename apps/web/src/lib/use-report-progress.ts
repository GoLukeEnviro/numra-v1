"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api, type ReportJobOut, type ReportOut } from "@/api/client";
import { isJobTerminal } from "@/lib/report-status";

export const REPORT_POLL_INTERVAL_MS = 2500;

/**
 * How many consecutive poll failures are tolerated before the whole view is put
 * into an error state. A single failed poll is usually a blip (a redeploy, a
 * rate-limit tick) and should not tear down a generation the user is watching.
 */
const MAX_CONSECUTIVE_POLL_FAILURES = 4;

/** The initial load lands immediately after this same page's own `POST /v1/reports`
 *  navigated here — a request that just barely missed a fully-settled backend (a
 *  redeploy, a load balancer still draining a stale backend) is exactly as much of
 *  a transient blip here as during polling, so it gets the same tolerance instead of
 *  permanently failing the page on the very first hiccup. */
const INITIAL_LOAD_MAX_ATTEMPTS = 3;
const INITIAL_LOAD_RETRY_DELAY_MS = 500;

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export type ReportProgress =
  | { phase: "loading" }
  | { phase: "error"; error: unknown }
  /** Generation is still running — `job` is null only until the first poll lands. */
  | { phase: "pending"; report: ReportOut; job: ReportJobOut | null }
  | { phase: "failed"; report: ReportOut; job: ReportJobOut | null }
  | { phase: "complete"; report: ReportOut };

/**
 * Loads a report and, while it is still generating, polls its job until the job
 * reaches a terminal state.
 *
 * Two deliberate properties:
 *  - The job's progress is never smoothed, extrapolated or assumed to increase.
 *    The queue retries with backoff and genuinely moves a job *backwards*
 *    (GENERATING → QUEUED → OUTLINE …), so whatever the API last reported is
 *    what is shown.
 *  - The report is re-fetched once the job reports COMPLETE, because the job row
 *    and the report row are separate; only `GET /v1/reports/{id}` carries content.
 */
export function useReportProgress(reportId: string): ReportProgress & { reload: () => void } {
  const [progress, setProgress] = useState<ReportProgress>({ phase: "loading" });
  const [reloadTick, setReloadTick] = useState(0);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const reload = useCallback(() => setReloadTick((t) => t + 1), []);

  useEffect(() => {
    let cancelled = false;
    let failureCount = 0;

    function clearTimer() {
      if (timerRef.current !== null) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
    }

    function settleFromReport(report: ReportOut, job: ReportJobOut | null) {
      if (report.status === "COMPLETE") {
        setProgress({ phase: "complete", report });
        return true;
      }
      if (report.status === "FAILED") {
        setProgress({ phase: "failed", report, job });
        return true;
      }
      return false;
    }

    async function poll(report: ReportOut) {
      let job: ReportJobOut;
      try {
        job = await api.reports.getJob(report.job_id);
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

      if (!isJobTerminal(job.status)) {
        setProgress({ phase: "pending", report, job });
        return;
      }

      // Terminal job: the report row is the authority on the outcome, so re-read it.
      clearTimer();
      try {
        const fresh = await api.reports.get(report.id);
        if (cancelled) return;
        if (!settleFromReport(fresh, job)) {
          // Job terminal but report not yet flipped (a cancelled run, or a write
          // still landing). Report what the job says rather than inventing a state.
          setProgress(
            job.status === "COMPLETE"
              ? { phase: "pending", report: fresh, job }
              : { phase: "failed", report: fresh, job },
          );
        }
      } catch (error) {
        if (!cancelled) setProgress({ phase: "error", error });
      }
    }

    async function start() {
      setProgress({ phase: "loading" });
      let report: ReportOut | undefined;
      let lastError: unknown;
      for (let attempt = 1; attempt <= INITIAL_LOAD_MAX_ATTEMPTS && !cancelled; attempt += 1) {
        try {
          report = await api.reports.get(reportId);
          break;
        } catch (error) {
          lastError = error;
          if (attempt < INITIAL_LOAD_MAX_ATTEMPTS) await delay(INITIAL_LOAD_RETRY_DELAY_MS);
        }
      }
      if (cancelled) return;
      if (report === undefined) {
        setProgress({ phase: "error", error: lastError });
        return;
      }

      if (settleFromReport(report, null)) return;

      setProgress({ phase: "pending", report, job: null });
      void poll(report);
      timerRef.current = setInterval(() => void poll(report), REPORT_POLL_INTERVAL_MS);
    }

    void start();

    return () => {
      cancelled = true;
      clearTimer();
    };
  }, [reportId, reloadTick]);

  return { ...progress, reload };
}
