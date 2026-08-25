"use client";

import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { NumericWheel } from "@/components/layout/numeric-wheel";
import type { ReportJobOut, ReportOut } from "@/api/client";
import { describeJobStatus, describeReportType, progressPercent } from "@/lib/report-status";
import { cn } from "@/lib/utils";
import { useLocale } from "@/i18n/context";
import { RotateCcw } from "lucide-react";

/**
 * The "your report is being written" view.
 *
 * Everything numeric here comes straight from the job row: the percentage is the
 * job's own `progress`, the attempt number is its own `attempt_count`. Nothing is
 * interpolated or animated towards a guessed value — while a job sits at 10% for
 * ten seconds, this shows 10%.
 *
 * Job status labels/descriptions (`lib/report-status.ts`) are a pure, non-React
 * lookup pinned by hardcoded-English assertions in its own test suite — they are
 * intentionally not routed through the locale catalog here (see final report).
 */
export function ReportProgressView({
  report,
  job,
}: {
  report: ReportOut;
  job: ReportJobOut | null;
}) {
  const { t } = useLocale();
  const status = describeJobStatus(job?.status ?? "QUEUED");
  const percent = job ? progressPercent(job.progress) : 0;

  return (
    <Card className="relative overflow-hidden shadow-elevated">
      <NumericWheel
        className="pointer-events-none absolute -right-16 -top-16 h-64 w-64 opacity-[0.12]"
      />
      <CardContent className="relative p-8 sm:p-10">
        <div className="flex flex-wrap items-center gap-3">
          <Badge variant="neutral">{describeReportType(report.report_type)}</Badge>
          <Badge variant={status.tone === "failed" ? "neutral" : "success"}>{status.label}</Badge>
        </div>

        <h2 className="mt-5 font-serif text-2xl text-ivory">{t("app.reportProgress.writing")}</h2>
        <p className="mt-2 max-w-reading text-sm text-muted">{status.description}</p>

        <div className="mt-8">
          <div
            className="h-1.5 w-full overflow-hidden rounded-full bg-white/10"
            role="progressbar"
            aria-valuenow={job ? job.progress : undefined}
            aria-valuemin={0}
            aria-valuemax={100}
            aria-label={t("app.reportProgress.aria")}
          >
            <div
              className={cn(
                "h-full rounded-full bg-gold transition-[width] duration-500 ease-out",
                !job && "animate-pulse",
              )}
              style={{ width: `${percent}%` }}
            />
          </div>
          <div className="mt-3 flex flex-wrap items-center justify-between gap-2 text-xs text-muted">
            <span aria-live="polite">
              {job ? `${job.progress}% · ${status.label}` : t("app.reportProgress.contacting")}
            </span>
            {job && job.attempt_count > 1 && (
              <span>
                {t("app.reportProgress.retriedPrefix")} {job.attempt_count}{" "}
                {t("app.reportProgress.retriedSuffix")}
              </span>
            )}
          </div>
        </div>

        <p className="mt-8 max-w-reading text-xs leading-relaxed text-muted">
          {t("app.reportProgress.checkNote")}
        </p>
      </CardContent>
    </Card>
  );
}

/**
 * Terminal failure. The backend's `error_code` is surfaced verbatim rather than
 * translated into a friendlier guess — an operator needs the real code, and this
 * client has no reliable mapping from code to cause.
 */
export function ReportFailedView({
  job,
  onRetry,
  retrying,
}: {
  job: ReportJobOut | null;
  onRetry: () => void;
  retrying: boolean;
}) {
  const { t } = useLocale();
  const status = describeJobStatus(job?.status ?? "FAILED");

  return (
    <Card className="border-danger/30 bg-danger-surface">
      <CardContent className="p-8">
        <h2 className="font-serif text-xl text-ivory">
          {t("app.reportFailed.title")} — {status.label.toLowerCase()}
        </h2>
        <p className="mt-2 max-w-reading text-sm text-text">{status.description}</p>

        {job?.error_code && (
          <p className="mt-4 text-sm text-text">
            <span className="mr-2 rounded bg-black/25 px-1.5 py-0.5 font-mono text-xs">
              {job.error_code}
            </span>
            {t("app.reportFailed.reportedBy")}
            {job.attempt_count > 1
              ? ` ${t("app.reportFailed.after")} ${job.attempt_count} ${t("app.reportFailed.afterAttempts")}`
              : ""}
            .
          </p>
        )}

        <p className="mt-4 max-w-reading text-sm text-muted">{t("app.reportFailed.untouched")}</p>

        <Button className="mt-6" variant="secondary" onClick={onRetry} loading={retrying}>
          <RotateCcw className="h-4 w-4" aria-hidden="true" />
          {t("app.reportFailed.retry")}
        </Button>
      </CardContent>
    </Card>
  );
}
