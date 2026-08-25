"use client";

import { useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { TraceList } from "@/components/analysis/trace-list";
import { NumericWheel } from "@/components/layout/numeric-wheel";
import type { CalculationMetric, ReductionResult, Timing } from "@/api/canonical-profile";
import { renderTrace } from "@/lib/trace";
import { formatIsoDate, cn } from "@/lib/utils";
import { useLocale } from "@/i18n/context";
import { ChevronDown } from "lucide-react";

/**
 * The numbers-only half of the Today view.
 *
 * Every value shown is a `display_value` returned by `GET /v1/people/{id}/timing`,
 * printed verbatim. Nothing in this component interprets, ranks or scores a number,
 * and nothing is computed in the browser — the only client-side logic is choosing
 * which of the four values gets the large type. The reflective counterpart lives in
 * `DailyBriefView` (V1.5 Epic K), rendered directly below this on the Today page.
 */

function MasterBadge({ masterNumber }: { masterNumber: number | null }) {
  const { t } = useLocale();
  if (masterNumber === null) return null;
  return (
    <Badge variant="master">
      {t("app.today.masterNumber")} {masterNumber}
    </Badge>
  );
}

function SupportingValue({
  label,
  displayValue,
  masterNumber,
}: {
  label: string;
  displayValue: string;
  masterNumber: number | null;
}) {
  return (
    <Card>
      <CardContent className="p-5">
        <p className="text-sm text-muted">{label}</p>
        <p className="mt-1.5 font-serif text-3xl text-gold">{displayValue}</p>
        <div className="mt-3 min-h-[1.25rem]">
          <MasterBadge masterNumber={masterNumber} />
        </div>
      </CardContent>
    </Card>
  );
}

function DerivationDisclosure({ metrics }: { metrics: { label: string; metric: CalculationMetric }[] }) {
  const { t } = useLocale();
  const [open, setOpen] = useState(false);

  return (
    <div className="mt-10">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        className="flex items-center gap-1.5 text-sm text-muted transition-colors hover:text-gold"
      >
        <ChevronDown
          className={cn("h-4 w-4 transition-transform", open && "rotate-180")}
          aria-hidden="true"
        />
        {open ? t("app.today.derivedHide") : t("app.today.derivedShow")}
      </button>

      {open && (
        <div className="mt-4 grid gap-4 sm:grid-cols-3">
          {metrics.map(({ label, metric }) => (
            <Card key={metric.metric_id}>
              <CardContent className="p-5">
                <p className="mb-3 text-sm text-ivory">{label}</p>
                <TraceList steps={renderTrace(metric)} />
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}

export function TimingView({
  personLabel,
  timing,
}: {
  personLabel: string;
  timing: Timing;
}) {
  const { t } = useLocale();
  const day: CalculationMetric = timing.personal_day;
  const universalYear: ReductionResult = timing.universal_year;

  return (
    <div className="animate-rise-in">
      <section className="sacred-wheel-bg relative overflow-hidden rounded-xl border border-white/10 bg-surface px-6 py-14 text-center shadow-elevated sm:px-10 sm:py-20">
        <NumericWheel className="pointer-events-none absolute left-1/2 top-1/2 h-[26rem] w-[26rem] -translate-x-1/2 -translate-y-1/2 opacity-[0.10]" />
        <div className="relative">
          <p className="text-xs uppercase tracking-[0.2em] text-bronze">Personal Day</p>
          <p className="mt-5 font-serif text-7xl leading-none text-gold sm:text-8xl">
            {day.display_value}
          </p>
          <p className="mt-6 text-sm text-muted">
            {personLabel} · {formatIsoDate(timing.as_of_date)}
          </p>
          {day.master_number !== null && (
            <div className="mt-5 flex justify-center">
              <MasterBadge masterNumber={day.master_number} />
            </div>
          )}
        </div>
      </section>

      <div className="mt-4 grid gap-4 sm:grid-cols-3">
        <SupportingValue
          label="Personal Month"
          displayValue={timing.personal_month.display_value}
          masterNumber={timing.personal_month.master_number}
        />
        <SupportingValue
          label="Personal Year"
          displayValue={timing.personal_year.display_value}
          masterNumber={timing.personal_year.master_number}
        />
        <SupportingValue
          label="Universal Year"
          displayValue={universalYear.display_value}
          masterNumber={universalYear.master_number}
        />
      </div>

      <DerivationDisclosure
        metrics={[
          { label: "Personal Day", metric: timing.personal_day },
          { label: "Personal Month", metric: timing.personal_month },
          { label: "Personal Year", metric: timing.personal_year },
        ]}
      />

      <p className="mt-8 max-w-reading text-xs leading-relaxed text-muted">
        {t("app.today.footnote")}
      </p>
    </div>
  );
}
