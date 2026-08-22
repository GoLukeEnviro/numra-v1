"use client";

import { Suspense } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { AppShell } from "@/components/layout/app-shell";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { LoadingState, ErrorState, EmptyState } from "@/components/ui/states";
import { api, type CalculationOut } from "@/api/client";
import { asCanonicalProfile, type CalculationMetric } from "@/api/canonical-profile";
import { useAsync } from "@/lib/use-async";
import { formatIsoDate } from "@/lib/utils";
import { ArrowLeft, Equal, GitCompareArrows } from "lucide-react";

/**
 * V1.5 Epic L: a factual, deterministic diff between two calculation snapshots of
 * the same person. Deliberately no "growth score", no ranking of which snapshot is
 * "better" -- core numbers are only expected to change if the underlying identity
 * (name/birth data) was edited between the two calculations (Epic B), and this view
 * exists to make that visible, not to judge it.
 */

const CORE_METRIC_IDS = [
  "life_path",
  "birthday",
  "attitude",
  "expression",
  "soul_urge",
  "personality",
  "maturity",
  "balance",
] as const;

const CORE_METRIC_LABELS: Record<(typeof CORE_METRIC_IDS)[number], string> = {
  life_path: "Life Path",
  birthday: "Birthday",
  attitude: "Attitude",
  expression: "Expression",
  soul_urge: "Soul Urge",
  personality: "Personality",
  maturity: "Maturity",
  balance: "Balance",
};

const TIMING_LABELS: Record<"personal_year" | "personal_month" | "personal_day", string> = {
  personal_year: "Personal Year",
  personal_month: "Personal Month",
  personal_day: "Personal Day",
};

function CoreNumberRow({
  label,
  a,
  b,
}: {
  label: string;
  a: CalculationMetric | undefined;
  b: CalculationMetric | undefined;
}) {
  const changed = a?.display_value !== b?.display_value;
  return (
    <div className="grid grid-cols-3 items-center gap-3 border-b border-white/5 py-2.5 text-sm last:border-0">
      <p className="text-muted">{label}</p>
      <p className={changed ? "font-medium text-gold" : "text-text"}>{a?.display_value ?? "—"}</p>
      <p className={changed ? "font-medium text-gold" : "text-text"}>{b?.display_value ?? "—"}</p>
    </div>
  );
}

function CompareContent({ aId, bId }: { aId: string; bId: string }) {
  const state = useAsync(
    () => Promise.all([api.calculations.get(aId), api.calculations.get(bId)]),
    [aId, bId],
  );

  if (state.status === "loading") return <LoadingState label="Loading both snapshots…" />;
  if (state.status === "error") {
    return (
      <ErrorState error={state.error} onRetry={state.reload} title="Could not load both snapshots" />
    );
  }

  const [calcA, calcB]: [CalculationOut, CalculationOut] = state.data;
  const profileA = asCanonicalProfile(calcA.canonical_profile);
  const profileB = asCanonicalProfile(calcB.canonical_profile);

  if (!profileA || !profileB) {
    return (
      <ErrorState
        error={new Error("A snapshot did not match the expected canonical profile shape.")}
        title="Unreadable snapshot"
        onRetry={state.reload}
      />
    );
  }

  if (calcA.person_id !== calcB.person_id) {
    return (
      <EmptyState
        title="These snapshots belong to different people"
        description="A comparison only makes sense between two calculations of the same person."
      />
    );
  }

  const coreChanged = CORE_METRIC_IDS.some(
    (id) => profileA.core_numbers[id].display_value !== profileB.core_numbers[id].display_value,
  );

  return (
    <div className="animate-rise-in">
      <Link
        href={`/people/${calcA.person_id}`}
        className="mb-6 inline-flex items-center gap-1.5 text-sm text-muted transition-colors hover:text-gold"
      >
        <ArrowLeft className="h-4 w-4" aria-hidden="true" />
        Back to profile
      </Link>

      <div className="mb-8">
        <h1 className="flex items-center gap-2 font-serif text-3xl text-ivory">
          <GitCompareArrows className="h-7 w-7 text-gold" aria-hidden="true" />
          Snapshot comparison
        </h1>
        <p className="mt-1 text-sm text-muted">
          {formatIsoDate(calcA.as_of_date)} vs. {formatIsoDate(calcB.as_of_date)}
        </p>
      </div>

      <div
        role="note"
        className="mb-6 rounded-xl border border-white/10 bg-surface-2 p-5 text-sm leading-relaxed text-muted"
      >
        This is a factual diff, nothing more: it shows which values differ between the two
        snapshots and stops there. Numra does not compute a growth score, an improvement
        percentage, or any judgment of which snapshot is &quot;better&quot;.
      </div>

      <Card className="mb-6">
        <CardHeader>
          <CardTitle className="text-base">Stable core numbers</CardTitle>
          <CardDescription>
            {coreChanged
              ? "These differ between the two snapshots — likely because the person's name or birth data was edited in between."
              : "Identical in both snapshots, as expected when the underlying identity has not changed."}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-3 gap-3 border-b border-white/10 pb-2 text-xs uppercase tracking-wider text-muted">
            <span>Metric</span>
            <span>{formatIsoDate(calcA.as_of_date)}</span>
            <span>{formatIsoDate(calcB.as_of_date)}</span>
          </div>
          {CORE_METRIC_IDS.map((id) => (
            <CoreNumberRow
              key={id}
              label={CORE_METRIC_LABELS[id]}
              a={profileA.core_numbers[id]}
              b={profileB.core_numbers[id]}
            />
          ))}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <div className="mb-1 flex items-center gap-2">
            <Equal className="h-4 w-4 text-muted" aria-hidden="true" />
            <CardTitle className="text-base">Date-dependent timing</CardTitle>
          </div>
          <CardDescription>
            Expected to differ — each snapshot was computed for a different as-of date.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-3 gap-3 border-b border-white/10 pb-2 text-xs uppercase tracking-wider text-muted">
            <span>Metric</span>
            <span>{formatIsoDate(calcA.as_of_date)}</span>
            <span>{formatIsoDate(calcB.as_of_date)}</span>
          </div>
          {(Object.keys(TIMING_LABELS) as (keyof typeof TIMING_LABELS)[]).map((id) => (
            <div
              key={id}
              className="grid grid-cols-3 items-center gap-3 border-b border-white/5 py-2.5 text-sm last:border-0"
            >
              <p className="text-muted">{TIMING_LABELS[id]}</p>
              <p className="text-text">{profileA.timing[id].display_value}</p>
              <p className="text-text">{profileB.timing[id].display_value}</p>
            </div>
          ))}
        </CardContent>
      </Card>
    </div>
  );
}

function CompareParamsGate() {
  const searchParams = useSearchParams();
  const aId = searchParams.get("a");
  const bId = searchParams.get("b");

  if (!aId || !bId) {
    return (
      <EmptyState
        title="Choose two snapshots"
        description="Open a person's profile, select two calculations from their history, and choose Compare."
      />
    );
  }

  return <CompareContent aId={aId} bId={bId} />;
}

export default function CompareCalculationsPage() {
  return (
    <AppShell>
      <Suspense fallback={<LoadingState label="Loading comparison…" />}>
        <CompareParamsGate />
      </Suspense>
    </AppShell>
  );
}
