"use client";

import { useMemo, useState } from "react";
import { AppShell } from "@/components/layout/app-shell";
import { Card, CardContent } from "@/components/ui/card";
import { Select } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { LinkButton } from "@/components/ui/link-button";
import { LoadingState, ErrorState, EmptyState } from "@/components/ui/states";
import { api, type ReportSummaryOut } from "@/api/client";
import { useAsync } from "@/lib/use-async";
import { describeReportType } from "@/lib/report-status";
import { formatDateTime } from "@/lib/utils";
import { useLocale } from "@/i18n/context";
import type { MessageKey } from "@/i18n/catalog";
import { BookOpen } from "lucide-react";

type StatusFilter = "all" | "PENDING" | "COMPLETE" | "FAILED";

const STATUS_TABS: { value: StatusFilter; labelKey: MessageKey }[] = [
  { value: "all", labelKey: "app.reports.filterAll" },
  { value: "PENDING", labelKey: "app.reports.filterPending" },
  { value: "COMPLETE", labelKey: "app.reports.filterComplete" },
  { value: "FAILED", labelKey: "app.reports.filterFailed" },
];

function statusBadgeVariant(status: string): "success" | "diagnostic" | "neutral" {
  if (status === "COMPLETE") return "success";
  if (status === "FAILED") return "diagnostic";
  return "neutral";
}

function ReportCard({ report }: { report: ReportSummaryOut }) {
  const { t } = useLocale();
  return (
    <Card>
      <CardContent className="flex flex-wrap items-center justify-between gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <p className="truncate text-text">{report.person.display_name}</p>
            <Badge variant="neutral">{describeReportType(report.report_type)}</Badge>
            <Badge variant={statusBadgeVariant(report.status)}>{report.status}</Badge>
          </div>
          <p className="mt-1 text-xs text-muted">
            {report.status === "COMPLETE" && report.generated_at
              ? `${t("app.reports.generated")} ${formatDateTime(report.generated_at)}`
              : `${t("app.reports.started")} ${formatDateTime(report.created_at)}`}
            {report.word_count > 0 && ` · ${report.word_count.toLocaleString()} ${t("app.reports.words")}`}
          </p>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <LinkButton size="sm" variant="secondary" href={`/analysis/${report.calculation_id}`}>
            {t("app.reports.openCalculation")}
          </LinkButton>
          <LinkButton size="sm" href={`/reports/${report.id}`}>
            {t("app.reports.open")}
          </LinkButton>
        </div>
      </CardContent>
    </Card>
  );
}

function ReportsContent() {
  const { t } = useLocale();
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [personFilter, setPersonFilter] = useState<string>("all");

  const peopleState = useAsync(() => api.people.list(), []);
  const reportsState = useAsync(
    () =>
      api.reports.list({
        status: statusFilter === "all" ? undefined : statusFilter,
        personId: personFilter === "all" ? undefined : personFilter,
      }),
    [statusFilter, personFilter],
  );

  const personOptions = useMemo(() => {
    const people = peopleState.status === "success" ? peopleState.data : [];
    return [...people].sort((a, b) => a.birth_first_names.localeCompare(b.birth_first_names));
  }, [peopleState]);

  return (
    <div>
      <div className="mb-8 flex items-center gap-3">
        <BookOpen className="h-6 w-6 text-gold" aria-hidden="true" />
        <div>
          <h1 className="font-serif text-3xl text-ivory">{t("app.reports.title")}</h1>
          <p className="mt-1 text-sm text-muted">{t("app.reports.subtitle")}</p>
        </div>
      </div>

      <div className="mb-6 flex flex-wrap items-center gap-3">
        <div
          className="flex flex-wrap gap-1.5"
          role="tablist"
          aria-label={t("app.reports.filterByStatus")}
        >
          {STATUS_TABS.map((tab) => (
            <button
              key={tab.value}
              type="button"
              role="tab"
              aria-selected={statusFilter === tab.value}
              onClick={() => setStatusFilter(tab.value)}
              className={`rounded-full px-3.5 py-1.5 text-sm transition-colors ${
                statusFilter === tab.value
                  ? "bg-gold text-background font-medium"
                  : "border border-white/15 text-muted hover:text-text"
              }`}
            >
              {t(tab.labelKey)}
            </button>
          ))}
        </div>
        <Select
          className="ml-auto w-auto min-w-[10rem]"
          value={personFilter}
          onChange={(e) => setPersonFilter(e.target.value)}
          aria-label={t("app.reports.filterByPerson")}
        >
          <option value="all">{t("app.reports.allPeople")}</option>
          {personOptions.map((person) => (
            <option key={person.id} value={person.id}>
              {person.preferred_name || `${person.birth_first_names} ${person.birth_last_name}`}
            </option>
          ))}
        </Select>
      </div>

      {reportsState.status === "loading" && <LoadingState label={t("app.reports.loading")} />}
      {reportsState.status === "error" && (
        <ErrorState
          error={reportsState.error}
          onRetry={reportsState.reload}
          title={t("app.reports.errorTitle")}
        />
      )}
      {reportsState.status === "success" && reportsState.data.length === 0 && (
        <EmptyState title={t("app.reports.emptyTitle")} description={t("app.reports.emptyBody")} />
      )}
      {reportsState.status === "success" && reportsState.data.length > 0 && (
        <div className="flex flex-col gap-3">
          {reportsState.data.map((report) => (
            <ReportCard key={report.id} report={report} />
          ))}
        </div>
      )}
    </div>
  );
}

export default function ReportsPage() {
  return (
    <AppShell>
      <ReportsContent />
    </AppShell>
  );
}
