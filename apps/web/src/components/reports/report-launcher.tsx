"use client";

import { useRef, useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { api, ApiError, type ReportType } from "@/api/client";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { LinkButton } from "@/components/ui/link-button";
import { REPORT_TYPE_OPTIONS } from "@/lib/report-status";
import { useAsync } from "@/lib/use-async";
import { formatDateTime } from "@/lib/utils";
import { cn } from "@/lib/utils";
import { BookOpen, ArrowRight } from "lucide-react";

/** A per-attempt Idempotency-Key, kept across retries of the *same* attempt so a
 *  resend after a network error re-joins the first job instead of queueing a second. */
function newIdempotencyKey(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  return `report-${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

export function ReportLauncher({ calculationId }: { calculationId: string }) {
  const router = useRouter();
  const [reportType, setReportType] = useState<ReportType>("FULL");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<{ code: string; message: string } | null>(null);
  const idempotencyKeyRef = useRef<string | null>(null);
  // Server-authoritative (V1.5 Epic A): a fresh browser context with no LocalStorage
  // still sees every report already started from this calculation.
  const previousState = useAsync(() => api.reports.list({ calculationId }), [calculationId]);
  const previous = previousState.status === "success" ? previousState.data : [];

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    idempotencyKeyRef.current ??= newIdempotencyKey();
    try {
      const report = await api.reports.create(
        { calculation_id: calculationId, report_type: reportType },
        idempotencyKeyRef.current,
      );
      idempotencyKeyRef.current = null;
      router.push(`/reports/${report.id}`);
    } catch (err) {
      setSubmitting(false);
      setError(
        err instanceof ApiError
          ? { code: err.code, message: err.message }
          : { code: "NETWORK_ERROR", message: "Could not reach the server." },
      );
    }
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center gap-2">
          <BookOpen className="h-5 w-5 text-gold" aria-hidden="true" />
          <CardTitle className="text-base">Written report</CardTitle>
        </div>
        <CardDescription>
          A long-form reading written from this exact calculation. Every number it states is
          verified against the canonical profile above before the report is assembled.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit}>
          <fieldset disabled={submitting}>
            <legend className="mb-3 text-sm font-medium text-ivory">Report length</legend>
            <div className="grid gap-3 sm:grid-cols-3">
              {REPORT_TYPE_OPTIONS.map((option) => {
                const selected = option.value === reportType;
                return (
                  <label
                    key={option.value}
                    className={cn(
                      "cursor-pointer rounded-lg border p-4 transition-colors",
                      selected
                        ? "border-gold/60 bg-gold/[0.07]"
                        : "border-white/10 bg-surface-2 hover:border-white/25",
                    )}
                  >
                    <span className="flex items-center gap-2">
                      <input
                        type="radio"
                        name="report-type"
                        value={option.value}
                        checked={selected}
                        onChange={() => setReportType(option.value)}
                        className="h-3.5 w-3.5 accent-gold"
                      />
                      <span
                        className={cn(
                          "font-serif text-base",
                          selected ? "text-gold" : "text-ivory",
                        )}
                      >
                        {option.label}
                      </span>
                    </span>
                    <span className="mt-2 block text-xs leading-relaxed text-muted">
                      {option.description}
                    </span>
                  </label>
                );
              })}
            </div>
          </fieldset>

          {error && (
            <div
              role="alert"
              className="mt-5 rounded-lg border border-danger/30 bg-danger-surface p-3 text-sm text-text"
            >
              <span className="mr-1.5 rounded bg-black/25 px-1.5 py-0.5 font-mono text-xs">
                {error.code}
              </span>
              {error.message}
            </div>
          )}

          <Button type="submit" className="mt-5" loading={submitting}>
            {submitting ? "Starting generation…" : "Generate report"}
          </Button>
        </form>

        {previous.length > 0 && (
          <div className="mt-6 border-t border-white/10 pt-5">
            <p className="mb-3 text-xs uppercase tracking-wider text-muted">
              Reports started from this calculation
            </p>
            <ul className="flex flex-col gap-2">
              {previous.map((entry) => (
                <li
                  key={entry.id}
                  className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-white/10 bg-surface-2 px-4 py-3"
                >
                  <div>
                    <p className="text-sm text-ivory">{entry.report_type}</p>
                    <p className="text-xs text-muted">Started {formatDateTime(entry.created_at)}</p>
                  </div>
                  <LinkButton size="sm" variant="secondary" href={`/reports/${entry.id}`}>
                    Open <ArrowRight className="h-3.5 w-3.5" aria-hidden="true" />
                  </LinkButton>
                </li>
              ))}
            </ul>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
