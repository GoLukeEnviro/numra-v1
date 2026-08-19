"use client";

import { useEffect } from "react";
import { useParams } from "next/navigation";
import { AppShell } from "@/components/layout/app-shell";
import { LoadingState, ErrorState } from "@/components/ui/states";
import { Tabs } from "@/components/ui/tabs";
import { CoreNumbersView } from "@/components/analysis/core-numbers-view";
import { InspectorView } from "@/components/analysis/inspector-view";
import { CyclesTimingView } from "@/components/analysis/cycles-timing-view";
import { api } from "@/api/client";
import { asCanonicalProfile } from "@/api/canonical-profile";
import { useAsync } from "@/lib/use-async";
import { recordCalculation } from "@/lib/local-calculations";
import { formatIsoDate } from "@/lib/utils";

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
    return <ErrorState error={calcState.error} onRetry={calcState.reload} title="Could not load this analysis" />;
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
      <div className="mb-2 flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <h1 className="font-serif text-3xl text-ivory">{name}</h1>
        <p className="text-sm text-muted">
          As of {formatIsoDate(calculation.as_of_date)} · calc.{" "}
          <code className="font-mono text-xs">{calculation.id}</code>
        </p>
      </div>
      <p className="mb-8 text-sm text-muted">
        {profile.calculation_system} v{profile.calculation_version} · schema v{profile.schema_version} ·
        hash{" "}
        <code className="font-mono text-xs">{calculation.deterministic_hash.slice(0, 12)}…</code>
      </p>

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
