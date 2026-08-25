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
import { useLocale } from "@/i18n/context";
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

// Numerology core-number labels are kept as the domain-standard English terms used
// throughout the calculation engine and canon-spec.md — see the final report's i18n
// scope note.
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
  const { t } = useLocale();
  const state = useAsync(
    () => Promise.all([api.calculations.get(aId), api.calculations.get(bId)]),
    [aId, bId],
  );

  if (state.status === "loading") return <LoadingState label={t("app.compare.loading")} />;
  if (state.status === "error") {
    return (
      <ErrorState error={state.error} onRetry={state.reload} title={t("app.compare.errorTitle")} />
    );
  }

  const [calcA, calcB]: [CalculationOut, CalculationOut] = state.data;
  const profileA = asCanonicalProfile(calcA.canonical_profile);
  const profileB = asCanonicalProfile(calcB.canonical_profile);

  if (!profileA || !profileB) {
    return (
      <ErrorState
        error={new Error("A snapshot did not match the expected canonical profile shape.")}
        title={t("app.compare.unreadableTitle")}
        onRetry={state.reload}
      />
    );
  }

  if (calcA.person_id !== calcB.person_id) {
    return (
      <EmptyState
        title={t("app.compare.differentPeopleTitle")}
        description={t("app.compare.differentPeopleBody")}
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
        {t("app.compare.back")}
      </Link>

      <div className="mb-8">
        <h1 className="flex items-center gap-2 font-serif text-3xl text-ivory">
          <GitCompareArrows className="h-7 w-7 text-gold" aria-hidden="true" />
          {t("app.compare.title")}
        </h1>
        <p className="mt-1 text-sm text-muted">
          {formatIsoDate(calcA.as_of_date)} vs. {formatIsoDate(calcB.as_of_date)}
        </p>
      </div>

      <div
        role="note"
        className="mb-6 rounded-xl border border-white/10 bg-surface-2 p-5 text-sm leading-relaxed text-muted"
      >
        {t("app.compare.factualNote")}
      </div>

      <Card className="mb-6">
        <CardHeader>
          <CardTitle className="text-base">{t("app.compare.stableTitle")}</CardTitle>
          <CardDescription>
            {coreChanged ? t("app.compare.stableChanged") : t("app.compare.stableUnchanged")}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-3 gap-3 border-b border-white/10 pb-2 text-xs uppercase tracking-wider text-muted">
            <span>{t("app.compare.metricColumn")}</span>
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
            <CardTitle className="text-base">{t("app.compare.timingTitle")}</CardTitle>
          </div>
          <CardDescription>{t("app.compare.timingBody")}</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-3 gap-3 border-b border-white/10 pb-2 text-xs uppercase tracking-wider text-muted">
            <span>{t("app.compare.metricColumn")}</span>
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
  const { t } = useLocale();
  const searchParams = useSearchParams();
  const aId = searchParams.get("a");
  const bId = searchParams.get("b");

  if (!aId || !bId) {
    return (
      <EmptyState title={t("app.compare.chooseTitle")} description={t("app.compare.chooseBody")} />
    );
  }

  return <CompareContent aId={aId} bId={bId} />;
}

export default function CompareCalculationsPage() {
  const { t } = useLocale();
  return (
    <AppShell>
      <Suspense fallback={<LoadingState label={t("app.compare.loadingOne")} />}>
        <CompareParamsGate />
      </Suspense>
    </AppShell>
  );
}
