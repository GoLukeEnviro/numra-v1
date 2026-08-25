"use client";

import { useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { AppShell } from "@/components/layout/app-shell";
import { LoadingState, ErrorState } from "@/components/ui/states";
import { ReportReader } from "@/components/reports/report-reader";
import { ReportProgressView, ReportFailedView } from "@/components/reports/report-progress-view";
import { ExportPanel } from "@/components/reports/export-panel";
import { api, ApiError, type ReportOut } from "@/api/client";
import { asStructuredReport } from "@/api/report-content";
import { useReportProgress } from "@/lib/use-report-progress";
import { useLocale } from "@/i18n/context";
import { ArrowLeft } from "lucide-react";

function BackToAnalysis({ calculationId }: { calculationId: string }) {
  const { t } = useLocale();
  return (
    <Link
      href={`/analysis/${calculationId}`}
      className="mb-6 inline-flex items-center gap-1.5 text-sm text-muted transition-colors hover:text-gold"
    >
      <ArrowLeft className="h-4 w-4" aria-hidden="true" />
      {t("app.reportDetail.back")}
    </Link>
  );
}

function ReportContent({ reportId }: { reportId: string }) {
  const router = useRouter();
  const { t } = useLocale();
  const progress = useReportProgress(reportId);
  const [retrying, setRetrying] = useState(false);
  const [retryError, setRetryError] = useState<{ code: string; message: string } | null>(null);

  /** A retry is a brand-new report from the same calculation — a failed report is
   *  never mutated or "resumed", so the audit trail keeps both runs. */
  async function retry(failed: ReportOut) {
    setRetrying(true);
    setRetryError(null);
    try {
      const report = await api.reports.create({
        calculation_id: failed.calculation_id,
        report_type: failed.report_type,
      });
      router.push(`/reports/${report.id}`);
    } catch (err) {
      setRetrying(false);
      setRetryError(
        err instanceof ApiError
          ? { code: err.code, message: err.message }
          : { code: "NETWORK_ERROR", message: t("common.networkError") },
      );
    }
  }

  if (progress.phase === "loading") {
    return <LoadingState label={t("app.reportDetail.loading")} />;
  }

  if (progress.phase === "error") {
    return (
      <ErrorState
        error={progress.error}
        onRetry={progress.reload}
        title={t("app.reportDetail.errorTitle")}
      />
    );
  }

  if (progress.phase === "pending") {
    return (
      <>
        <BackToAnalysis calculationId={progress.report.calculation_id} />
        <ReportProgressView report={progress.report} job={progress.job} />
      </>
    );
  }

  if (progress.phase === "failed") {
    return (
      <>
        <BackToAnalysis calculationId={progress.report.calculation_id} />
        <ReportFailedView
          job={progress.job}
          onRetry={() => void retry(progress.report)}
          retrying={retrying}
        />
        {retryError && (
          <div
            role="alert"
            className="mt-4 rounded-lg border border-danger/30 bg-danger-surface p-3 text-sm text-text"
          >
            <span className="mr-1.5 rounded bg-black/25 px-1.5 py-0.5 font-mono text-xs">
              {retryError.code}
            </span>
            {retryError.message}
          </div>
        )}
      </>
    );
  }

  const content = asStructuredReport(progress.report.content);
  if (!content) {
    return (
      <>
        <BackToAnalysis calculationId={progress.report.calculation_id} />
        <ErrorState
          error={new Error(
            "The report is marked complete but its stored content did not match the expected structure.",
          )}
          title={t("app.reportDetail.unreadableTitle")}
          onRetry={progress.reload}
        />
      </>
    );
  }

  return (
    <>
      <BackToAnalysis calculationId={progress.report.calculation_id} />
      <ReportReader report={progress.report} content={content} />
      <div className="mt-12 max-w-reading">
        <ExportPanel reportId={progress.report.id} />
      </div>
    </>
  );
}

export default function ReportPage() {
  const params = useParams<{ reportId: string }>();
  return (
    <AppShell>
      <ReportContent reportId={params.reportId} />
    </AppShell>
  );
}
