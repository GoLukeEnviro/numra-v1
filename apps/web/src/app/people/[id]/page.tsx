"use client";

import { useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { AppShell } from "@/components/layout/app-shell";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { LinkButton } from "@/components/ui/link-button";
import { LoadingState, ErrorState } from "@/components/ui/states";
import { NumericWheel } from "@/components/layout/numeric-wheel";
import { IdentityTimeline } from "@/components/people/identity-timeline";
import { api, ApiError, type PersonOut } from "@/api/client";
import { useAsync } from "@/lib/use-async";
import { recordCalculation, getLatestForPerson } from "@/lib/local-calculations";
import { personDisplayName } from "@/lib/identity";
import { formatDateTime, formatIsoDate, todayIsoDate } from "@/lib/utils";
import { useLocale } from "@/i18n/context";
import { Sparkles, Trash2, Sunrise, ArrowRight, Pencil, History } from "lucide-react";

function DetailRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="border-b border-white/5 py-3 last:border-0 first:pt-0 last:pb-0">
      <dt className="text-xs uppercase tracking-wider text-muted">{label}</dt>
      <dd className="mt-1 text-sm text-text">{children}</dd>
    </div>
  );
}

function BirthDataCard({ person }: { person: PersonOut }) {
  const { t } = useLocale();
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">{t("app.personDetail.birthDataTitle")}</CardTitle>
        <CardDescription>{t("app.personDetail.birthDataBody")}</CardDescription>
      </CardHeader>
      <CardContent>
        <dl>
          <DetailRow label={t("app.personDetail.birthDate")}>
            {formatIsoDate(person.birth_date)}
          </DetailRow>
          <DetailRow label={t("app.personDetail.birthTime")}>
            {person.birth_time?.value ? (
              <>
                {person.birth_time.value}{" "}
                <span className="text-muted">({person.birth_time.precision})</span>
              </>
            ) : (
              <span className="text-muted">{t("app.personDetail.notRecorded")}</span>
            )}
          </DetailRow>
          <DetailRow label={t("app.personDetail.birthPlace")}>
            {person.birth_place?.display_name ? (
              <>
                {person.birth_place.display_name}
                {person.birth_place.country_code && (
                  <span className="text-muted"> · {person.birth_place.country_code}</span>
                )}
              </>
            ) : (
              <span className="text-muted">{t("app.personDetail.notRecorded")}</span>
            )}
          </DetailRow>
        </dl>
      </CardContent>
    </Card>
  );
}

/** Server-authoritative (V1.5 Epic A/L): every snapshot this person has ever had,
 *  visible from any device, newest first. Immutable — nothing here can be edited.
 *  Selecting exactly two enables a snapshot comparison (Epic L). */
function CalculationHistoryCard({ personId }: { personId: string }) {
  const router = useRouter();
  const { t } = useLocale();
  const state = useAsync(() => api.calculations.list(personId), [personId]);
  const [selected, setSelected] = useState<string[]>([]);

  function toggle(id: string) {
    setSelected((current) => {
      if (current.includes(id)) return current.filter((c) => c !== id);
      const mostRecent = current[current.length - 1];
      if (current.length >= 2 && mostRecent) return [mostRecent, id];
      return [...current, id];
    });
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center gap-2">
          <History className="h-4 w-4 text-gold" aria-hidden="true" />
          <CardTitle className="text-base">{t("app.personDetail.historyTitle")}</CardTitle>
        </div>
        <CardDescription>{t("app.personDetail.historyBody")}</CardDescription>
      </CardHeader>
      <CardContent>
        {state.status === "loading" && <p className="text-sm text-muted">{t("common.loading")}</p>}
        {state.status === "error" && (
          <p className="text-sm text-danger">{t("app.personDetail.historyError")}</p>
        )}
        {state.status === "success" && state.data.length === 0 && (
          <p className="text-sm text-muted">{t("app.personDetail.noCalculations")}</p>
        )}
        {state.status === "success" && state.data.length > 0 && (
          <>
            <ul className="flex flex-col gap-2">
              {state.data.map((calc) => {
                const isSelected = selected.includes(calc.id);
                return (
                  <li
                    key={calc.id}
                    className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-white/10 bg-surface-2 px-4 py-2.5"
                  >
                    <label className="flex items-center gap-3">
                      <input
                        type="checkbox"
                        checked={isSelected}
                        onChange={() => toggle(calc.id)}
                        aria-label={`${t("app.personDetail.selectSnapshotAria")} ${formatIsoDate(calc.as_of_date)}`}
                        className="h-4 w-4 rounded border-white/20 bg-surface text-gold accent-gold"
                      />
                      <div>
                        <p className="text-sm text-text">
                          {t("app.personDetail.asOf")} {formatIsoDate(calc.as_of_date)}
                        </p>
                        <p className="font-mono text-xs text-muted">
                          {calc.deterministic_hash.slice(0, 12)} · {formatDateTime(calc.created_at)}
                        </p>
                      </div>
                    </label>
                    <LinkButton size="sm" variant="secondary" href={`/analysis/${calc.id}`}>
                      {t("app.personDetail.open")} <ArrowRight className="h-3.5 w-3.5" aria-hidden="true" />
                    </LinkButton>
                  </li>
                );
              })}
            </ul>
            <div className="mt-4 flex items-center gap-3">
              <Button
                type="button"
                size="sm"
                disabled={selected.length !== 2}
                onClick={() =>
                  router.push(`/calculations/compare?a=${selected[0]}&b=${selected[1]}`)
                }
              >
                {t("app.personDetail.compareSelected")}
              </Button>
              <p className="text-xs text-muted">
                {selected.length === 0 && t("app.personDetail.selectTwo")}
                {selected.length === 1 && t("app.personDetail.selectOneMore")}
                {selected.length === 2 && t("app.personDetail.readyToCompare")}
              </p>
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}

function DangerZone({
  onDelete,
  deleting,
}: {
  onDelete: () => void;
  deleting: boolean;
}) {
  const { t } = useLocale();
  const [confirming, setConfirming] = useState(false);

  return (
    <Card className="border-danger/25">
      <CardHeader>
        <CardTitle className="text-base">{t("app.personDetail.deleteTitle")}</CardTitle>
        <CardDescription>{t("app.personDetail.deleteBody")}</CardDescription>
      </CardHeader>
      <CardContent>
        {confirming ? (
          <div className="flex flex-wrap items-center gap-3">
            <Button variant="danger" onClick={onDelete} loading={deleting}>
              <Trash2 className="h-4 w-4" aria-hidden="true" />
              {t("app.personDetail.deleteConfirm")}
            </Button>
            <Button variant="ghost" onClick={() => setConfirming(false)} disabled={deleting}>
              {t("app.personDetail.deleteCancel")}
            </Button>
          </div>
        ) : (
          <Button variant="secondary" onClick={() => setConfirming(true)}>
            <Trash2 className="h-4 w-4" aria-hidden="true" />
            {t("app.personDetail.deleteButton")}
          </Button>
        )}
      </CardContent>
    </Card>
  );
}

function PersonDetailContent({ personId }: { personId: string }) {
  const router = useRouter();
  const { t } = useLocale();
  const personState = useAsync(() => api.people.get(personId), [personId]);
  const [calcRunning, setCalcRunning] = useState(false);
  const [actionError, setActionError] = useState<{ code: string; message: string } | null>(null);
  const [deleting, setDeleting] = useState(false);
  const cached = getLatestForPerson(personId);

  function reportError(err: unknown) {
    setActionError(
      err instanceof ApiError
        ? { code: err.code, message: err.message }
        : { code: "NETWORK_ERROR", message: t("common.networkError") },
    );
  }

  async function runCalculation() {
    setCalcRunning(true);
    setActionError(null);
    try {
      const asOfDate = todayIsoDate();
      const calculation = await api.calculations.create(personId, { as_of_date: asOfDate });
      if (personState.status === "success") {
        recordCalculation({
          calculationId: calculation.id,
          personId,
          personLabel: personDisplayName(personState.data),
          asOfDate,
        });
      }
      router.push(`/analysis/${calculation.id}`);
    } catch (err) {
      setCalcRunning(false);
      reportError(err);
    }
  }

  async function handleDelete() {
    setDeleting(true);
    setActionError(null);
    try {
      await api.people.remove(personId);
      router.push("/people");
    } catch (err) {
      setDeleting(false);
      reportError(err);
    }
  }

  if (personState.status === "loading") return <LoadingState label={t("app.personDetail.loadingProfile")} />;
  if (personState.status === "error") {
    return <ErrorState error={personState.error} onRetry={personState.reload} />;
  }

  const person = personState.data;
  const label = personDisplayName(person);

  return (
    <div className="animate-rise-in">
      <header className="sacred-wheel-bg-left relative mb-6 overflow-hidden rounded-xl border border-white/10 bg-surface p-6 shadow-elevated sm:p-8">
        <NumericWheel className="pointer-events-none absolute -right-16 -top-20 h-56 w-56 opacity-[0.12]" />
        <div className="relative flex flex-wrap items-end justify-between gap-6">
          <div className="min-w-0">
            <p className="mb-2 text-xs uppercase tracking-wider text-bronze">
              {t("app.personDetail.eyebrow")}
            </p>
            <h1 className="font-serif text-3xl text-ivory sm:text-4xl">{label}</h1>
            <p className="mt-2 text-sm text-muted">
              {t("app.people.born")} {formatIsoDate(person.birth_date)}
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button onClick={runCalculation} loading={calcRunning}>
              <Sparkles className="h-4 w-4" aria-hidden="true" />
              {t("app.people.runCalculation")}
            </Button>
            {cached && (
              <LinkButton variant="secondary" href={`/analysis/${cached.calculationId}`}>
                {t("app.personDetail.lastAnalysis")} <ArrowRight className="h-4 w-4" aria-hidden="true" />
              </LinkButton>
            )}
            <LinkButton variant="ghost" href="/today">
              <Sunrise className="h-4 w-4" aria-hidden="true" />
              {t("app.personDetail.today")}
            </LinkButton>
            <LinkButton variant="ghost" href={`/people/${personId}/edit`}>
              <Pencil className="h-4 w-4" aria-hidden="true" />
              {t("app.personDetail.edit")}
            </LinkButton>
          </div>
        </div>
      </header>

      {actionError && (
        <div
          role="alert"
          className="mb-6 rounded-lg border border-danger/30 bg-danger-surface p-3 text-sm text-text"
        >
          <span className="mr-1.5 rounded bg-black/25 px-1.5 py-0.5 font-mono text-xs">
            {actionError.code}
          </span>
          {actionError.message}
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-2">
        <IdentityTimeline person={person} />
        <BirthDataCard person={person} />
      </div>

      <div className="mt-6">
        <CalculationHistoryCard personId={personId} />
      </div>

      <div className="mt-6 max-w-xl">
        <DangerZone onDelete={handleDelete} deleting={deleting} />
      </div>
    </div>
  );
}

export default function PersonDetailPage() {
  const params = useParams<{ id: string }>();
  return (
    <AppShell>
      <PersonDetailContent personId={params.id} />
    </AppShell>
  );
}
