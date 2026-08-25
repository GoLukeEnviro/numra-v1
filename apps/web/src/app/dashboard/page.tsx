"use client";

import Link from "next/link";
import { AppShell } from "@/components/layout/app-shell";
import { api, type PersonOut } from "@/api/client";
import { useAsync } from "@/lib/use-async";
import { useLocale } from "@/i18n/context";
import { LoadingState, ErrorState, EmptyState } from "@/components/ui/states";
import { Card, CardContent } from "@/components/ui/card";
import { LinkButton } from "@/components/ui/link-button";
import { NumericWheel } from "@/components/layout/numeric-wheel";
import { getLatestForPerson } from "@/lib/local-calculations";
import { personDisplayName } from "@/lib/identity";
import { formatIsoDate } from "@/lib/utils";
import {
  ArrowRight,
  Sparkles,
  UserPlus,
  Sunrise,
  GitCompareArrows,
  type LucideIcon,
} from "lucide-react";

function DashboardHero({ personCount }: { personCount: number | null }) {
  const { t } = useLocale();
  return (
    <header className="sacred-wheel-bg-left relative mb-6 overflow-hidden rounded-xl border border-white/10 bg-surface p-6 shadow-elevated sm:p-10">
      <NumericWheel className="pointer-events-none absolute -right-24 -top-28 h-80 w-80 opacity-[0.13]" />
      <div className="relative max-w-reading">
        <p className="mb-3 text-xs uppercase tracking-[0.2em] text-bronze">{t("app.dashboard.eyebrow")}</p>
        <h1 className="font-serif text-3xl text-ivory sm:text-4xl">
          {t("app.dashboard.heroTitle")}
        </h1>
        <p className="mt-3 text-sm leading-relaxed text-muted">
          {t("app.dashboard.heroBody")}
        </p>
        {personCount !== null && (
          <p className="mt-6 text-sm text-muted">
            <span className="font-serif text-2xl text-gold">{personCount}</span>{" "}
            {personCount === 1 ? t("app.dashboard.profileSingular") : t("app.dashboard.profilePlural")}
          </p>
        )}
      </div>
    </header>
  );
}

function QuickAction({
  href,
  icon: Icon,
  title,
  description,
}: {
  href: string;
  icon: LucideIcon;
  title: string;
  description: string;
}) {
  const { t } = useLocale();
  return (
    <Link
      href={href}
      className="group flex flex-col rounded-xl border border-white/10 bg-surface p-5 transition-colors hover:border-gold/40 hover:bg-surface-2"
    >
      <span className="flex items-center gap-2.5">
        <Icon className="h-4 w-4 text-gold" aria-hidden="true" />
        <span className="font-serif text-base text-ivory">{title}</span>
      </span>
      <span className="mt-2 text-xs leading-relaxed text-muted">{description}</span>
      <span className="mt-3 inline-flex items-center gap-1 text-xs text-muted transition-colors group-hover:text-gold">
        {t("app.dashboard.qaOpen")} <ArrowRight className="h-3 w-3" aria-hidden="true" />
      </span>
    </Link>
  );
}

function PersonCard({ person }: { person: PersonOut }) {
  const { t } = useLocale();
  const cached = getLatestForPerson(person.id);

  return (
    <Card className="transition-colors hover:border-white/20">
      <CardContent className="flex h-full flex-col p-5">
        <div className="flex-1">
          <p className="font-serif text-xl text-ivory">{personDisplayName(person)}</p>
          <p className="mt-1 text-sm text-muted">{t("app.people.born")} {formatIsoDate(person.birth_date)}</p>
          <p className="mt-3 text-xs text-muted">
            {cached
              ? `${t("app.dashboard.lastAnalysisPrefix")} ${formatIsoDate(cached.asOfDate)}`
              : t("app.dashboard.noAnalysisYet")}
          </p>
        </div>
        <div className="mt-5 flex flex-wrap gap-2">
          {cached ? (
            <LinkButton variant="secondary" size="sm" href={`/analysis/${cached.calculationId}`}>
              {t("app.dashboard.viewAnalysis")} <ArrowRight className="h-4 w-4" aria-hidden="true" />
            </LinkButton>
          ) : (
            <LinkButton size="sm" href={`/people/${person.id}`}>
              <Sparkles className="h-4 w-4" aria-hidden="true" />
              {t("app.people.runCalculation")}
            </LinkButton>
          )}
          <LinkButton variant="ghost" size="sm" href={`/people/${person.id}`}>
            {t("app.dashboard.profileLink")}
          </LinkButton>
        </div>
      </CardContent>
    </Card>
  );
}

function DashboardContent() {
  const { t } = useLocale();
  const peopleState = useAsync(() => api.people.list(), []);
  const personCount = peopleState.status === "success" ? peopleState.data.length : null;

  return (
    <div className="animate-rise-in">
      <DashboardHero personCount={personCount} />

      <div className="mb-10 grid gap-3 sm:grid-cols-3">
        <QuickAction
          href="/today"
          icon={Sunrise}
          title={t("app.dashboard.qaTodayTitle")}
          description={t("app.dashboard.qaTodayBody")}
        />
        <QuickAction
          href="/people/new"
          icon={UserPlus}
          title={t("app.dashboard.qaNewProfileTitle")}
          description={t("app.dashboard.qaNewProfileBody")}
        />
        <QuickAction
          href="/relationships"
          icon={GitCompareArrows}
          title={t("app.dashboard.qaCompareTitle")}
          description={t("app.dashboard.qaCompareBody")}
        />
      </div>

      <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
        <h2 className="font-serif text-xl text-ivory">{t("app.dashboard.yourPeople")}</h2>
        <LinkButton href="/people/new" size="sm" variant="secondary">
          <UserPlus className="h-4 w-4" aria-hidden="true" />
          {t("app.people.newProfile")}
        </LinkButton>
      </div>

      {peopleState.status === "loading" && <LoadingState label={t("app.dashboard.loadingPeople")} />}
      {peopleState.status === "error" && (
        <ErrorState error={peopleState.error} onRetry={peopleState.reload} />
      )}
      {peopleState.status === "success" && peopleState.data.length === 0 && (
        <EmptyState
          title={t("app.people.emptyTitle")}
          description={t("app.people.emptyBody")}
          action={
            <LinkButton href="/people/new">
              <UserPlus className="h-4 w-4" aria-hidden="true" />
              {t("app.people.newProfile")}
            </LinkButton>
          }
        />
      )}
      {peopleState.status === "success" && peopleState.data.length > 0 && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {peopleState.data.map((person) => (
            <PersonCard key={person.id} person={person} />
          ))}
        </div>
      )}
    </div>
  );
}

export default function DashboardPage() {
  return (
    <AppShell>
      <DashboardContent />
    </AppShell>
  );
}
