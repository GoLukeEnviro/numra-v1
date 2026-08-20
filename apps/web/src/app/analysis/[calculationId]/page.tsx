"use client";

import { useEffect } from "react";
import { useParams } from "next/navigation";
import { AppShell } from "@/components/layout/app-shell";
import { LoadingState, ErrorState } from "@/components/ui/states";
import { Tabs } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import { NumericWheel } from "@/components/layout/numeric-wheel";
import { CoreNumbersView } from "@/components/analysis/core-numbers-view";
import { InspectorView } from "@/components/analysis/inspector-view";
import { CyclesTimingView } from "@/components/analysis/cycles-timing-view";
import { ReportLauncher } from "@/components/reports/report-launcher";
import { api } from "@/api/client";
import { asCanonicalProfile } from "@/api/canonical-profile";
import { useAsync } from "@/lib/use-async";
import { recordCalculation } from "@/lib/local-calculations";
import { formatIsoDate } from "@/lib/utils";
import { BookOpen } from "lucide-react";

function AnalysisContent({ calculationId }: { calculationId: string }) {
  const calcState = useAsync(() => api.calculations.get(calculationId), [calculationId]);

  useEffect(() => {
    if (calcState.status !== "success") return;
    const profile = asCanonicalProfile(calcState.data.canonical_profile);
    if (!profile) return;
    recordCalculation({
      calculationId: calcState.data.id,
      personId: calcState.data.person_id,
      personLabel: `${profile.person.birth_first_names} ${profile.person.birth_last_name}`,
      asOfDate: calcState.data.as_of_date,
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [calcState.status]);

  if (calcState.status === "loading") return <LoadingState label="Loading calculation…" />;
  if (calcState.status === "error") {
    return (
      <ErrorState
        error={calcState.error}
        onRetry={calcState.reload}
        title="Could not load this analysis"
      />
    );
  }

  const calculation = calcState.data;
  const profile = asCanonicalProfile(calculation.canonical_profile);

  if (!profile) {
    return (
      <ErrorState
        error={new Error("The calculation payload did not match the expected canonical profile shape.")}
        title="Unreadable calculation"
      />
    );
  }

  const name = `${profile.person.birth_first_names} ${profile.person.birth_last_name}`.trim();

  return (
    <div>
      <header className="sacred-wheel-bg-left relative mb-10 animate-rise-in overflow-hidden rounded-xl border border-white/10 bg-surface p-6 shadow-elevated sm:p-8">
        <NumericWheel className="pointer-events-none absolute -right-16 -top-20 h-64 w-64 opacity-[0.13]" />
        <div className="relative flex flex-wrap items-start justify-between gap-6">
          <div className="min-w-0">
            <p className="mb-2 text-xs uppercase tracking-wider text-bronze">Calculation</p>
            <h1 className="font-serif text-3xl text-ivory sm:text-4xl">{name}</h1>
            <p className="mt-2 text-sm text-muted">As of {formatIsoDate(calculation.as_of_date)}</p>
            <div className="mt-5 flex flex-wrap items-center gap-2">
              <Badge variant="neutral">
                {profile.calculation_system} v{profile.calculation_version}
              </Badge>
              <Badge variant="neutral">schema v{profile.schema_version}</Badge>
              <Badge variant="neutral" title={calculation.deterministic_hash}>
                hash {calculation.deterministic_hash.slice(0, 12)}…
              </Badge>
            </div>
          </div>
          <a
            href="#written-report"
            className="inline-flex h-10 shrink-0 items-center gap-2 rounded-lg bg-gold px-4 text-sm font-medium text-background transition-colors hover:bg-gold/90"
          >
            <BookOpen className="h-4 w-4" aria-hidden="true" />
            Written report
          </a>
        </div>
        <p className="relative mt-6 max-w-reading border-t border-white/10 pt-5 text-xs leading-relaxed text-muted">
          This snapshot is immutable. Re-running the same person on the same as-of date
          reproduces the identical hash above — every value on this page traces back to its
          inputs, step by step.
        </p>
      </header>

      <Tabs
        tabs={[
          {
            id: "core-numbers",
            label: "Core Numbers",
            content: <CoreNumbersView core={profile.core_numbers} />,
          },
          {
            id: "inspector",
            label: "Calculation Inspector",
            content: <InspectorView core={profile.core_numbers} diagnostics={profile.diagnostics} />,
          },
          {
            id: "cycles-timing",
            label: "Cycles & Timing",
            content: <CyclesTimingView cycles={profile.cycles} timing={profile.timing} />,
          },
        ]}
      />

      <section id="written-report" className="mt-14 scroll-mt-8">
        <h2 className="mb-4 font-serif text-xl text-ivory">Written report</h2>
        <ReportLauncher calculationId={calculation.id} personLabel={name} />
      </section>
    </div>
  );
}

export default function AnalysisPage() {
  const params = useParams<{ calculationId: string }>();
  return (
    <AppShell>
      <AnalysisContent calculationId={params.calculationId} />
    </AppShell>
  );
}
