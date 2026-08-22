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
import { BookOpen } from "lucide-react";

type StatusFilter = "all" | "PENDING" | "COMPLETE" | "FAILED";

const STATUS_TABS: { value: StatusFilter; label: string }[] = [
  { value: "all", label: "All" },
  { value: "PENDING", label: "In progress" },
  { value: "COMPLETE", label: "Complete" },
  { value: "FAILED", label: "Failed" },
];

function statusBadgeVariant(status: string): "success" | "diagnostic" | "neutral" {
  if (status === "COMPLETE") return "success";
  if (status === "FAILED") return "diagnostic";
  return "neutral";
}

function ReportCard({ report }: { report: ReportSummaryOut }) {
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
              ? `Generated ${formatDateTime(report.generated_at)}`
              : `Started ${formatDateTime(report.created_at)}`}
            {report.word_count > 0 && ` · ${report.word_count.toLocaleString()} words`}
          </p>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <LinkButton size="sm" variant="secondary" href={`/analysis/${report.calculation_id}`}>
            Calculation
          </LinkButton>
          <LinkButton size="sm" href={`/reports/${report.id}`}>
            Open
          </LinkButton>
        </div>
      </CardContent>
    </Card>
  );
}

function ReportsContent() {
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
          <h1 className="font-serif text-3xl text-ivory">Reports</h1>
          <p className="mt-1 text-sm text-muted">
            Every long-form reading you have generated — server-side, visible from any device.
          </p>
        </div>
      </div>

      <div className="mb-6 flex flex-wrap items-center gap-3">
        <div className="flex flex-wrap gap-1.5" role="tablist" aria-label="Filter by status">
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
              {tab.label}
            </button>
          ))}
        </div>
        <Select
          className="ml-auto w-auto min-w-[10rem]"
          value={personFilter}
          onChange={(e) => setPersonFilter(e.target.value)}
          aria-label="Filter by person"
        >
          <option value="all">All people</option>
          {personOptions.map((person) => (
            <option key={person.id} value={person.id}>
              {person.preferred_name || `${person.birth_first_names} ${person.birth_last_name}`}
            </option>
          ))}
        </Select>
      </div>

      {reportsState.status === "loading" && <LoadingState label="Loading reports…" />}
      {reportsState.status === "error" && (
        <ErrorState
          error={reportsState.error}
          onRetry={reportsState.reload}
          title="Could not load your reports"
        />
      )}
      {reportsState.status === "success" && reportsState.data.length === 0 && (
        <EmptyState
          title="No reports yet"
          description="Generate a report from any calculation's Analysis page to see it here."
        />
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
