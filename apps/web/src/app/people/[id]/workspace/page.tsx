"use client";

import type { ReactNode } from "react";
import { useParams } from "next/navigation";
import { AppShell } from "@/components/layout/app-shell";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { LinkButton } from "@/components/ui/link-button";
import { LoadingState, ErrorState } from "@/components/ui/states";
import { WorkspaceHeader } from "@/components/workspace/workspace-header";
import { PersonalTasksPanel } from "@/components/workspace/personal-tasks-panel";
import { PrivateNotesPanel } from "@/components/workspace/private-notes-panel";
import { PrivateReflectionsPanel } from "@/components/workspace/private-reflections-panel";
import { api, type MyWorkspaceOverviewOut } from "@/api/client";
import { useAsync } from "@/lib/use-async";
import { formatDateTime } from "@/lib/utils";
import { useLocale } from "@/i18n/context";
import { ArrowRight } from "lucide-react";

function ClusterCard({
  eyebrow,
  title,
  description,
  children,
}: {
  eyebrow: string;
  title: string;
  description: string;
  children?: ReactNode;
}) {
  return (
    <section>
      <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-bronze">{eyebrow}</p>
      <Card>
        <CardHeader>
          <CardTitle className="text-base">{title}</CardTitle>
          <CardDescription>{description}</CardDescription>
        </CardHeader>
        {children && <CardContent>{children}</CardContent>}
      </Card>
    </section>
  );
}

/**
 * Functional clusters, not ~15 near-identical single cards: PROFIL/MUSTER/AKTUELL
 * link out to the real existing surfaces that already render this content; only
 * ARBEITEN (the three private panels) is genuinely new here.
 */
function WorkspaceOverview({ personId, overview }: { personId: string; overview: MyWorkspaceOverviewOut }) {
  const { t } = useLocale();
  const managedProfile = overview.person.person_account_mode !== "SELF";

  return (
    <div className="flex flex-col gap-8">
      <ClusterCard
        eyebrow={t("app.workspace.clusterProfileTitle")}
        title={t("app.workspace.clusterProfileTitle")}
        description={t("app.workspace.clusterProfileBody")}
      >
        <LinkButton href={`/people/${personId}`} variant="secondary" size="sm">
          {t("app.workspace.clusterProfileCta")} <ArrowRight className="h-3.5 w-3.5" aria-hidden="true" />
        </LinkButton>
      </ClusterCard>

      <ClusterCard
        eyebrow={t("app.workspace.clusterPatternTitle")}
        title={t("app.workspace.clusterPatternTitle")}
        description={t("app.workspace.clusterPatternBody")}
      >
        {overview.latest_calculation ? (
          <LinkButton href={`/analysis/${overview.latest_calculation.id}`} variant="secondary" size="sm">
            {t("app.workspace.clusterPatternCta")} <ArrowRight className="h-3.5 w-3.5" aria-hidden="true" />
          </LinkButton>
        ) : (
          <p className="text-sm text-muted">{t("app.workspace.clusterPatternEmpty")}</p>
        )}
      </ClusterCard>

      <ClusterCard
        eyebrow={t("app.workspace.clusterTimingTitle")}
        title={t("app.workspace.clusterTimingTitle")}
        description={t("app.workspace.clusterTimingBody")}
      >
        <LinkButton href={`/today?person_id=${personId}`} variant="secondary" size="sm">
          {t("app.workspace.clusterTimingCta")} <ArrowRight className="h-3.5 w-3.5" aria-hidden="true" />
        </LinkButton>
      </ClusterCard>

      <section>
        <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-bronze">
          {t("app.workspace.clusterWorkingTitle")}
        </p>
        <p className="mb-4 max-w-reading text-sm text-muted">{t("app.workspace.clusterWorkingBody")}</p>
        <div className="flex flex-col gap-4">
          <PersonalTasksPanel
            personId={personId}
            managedProfile={managedProfile}
            initialActiveCount={overview.personal_tasks.active}
          />
          <PrivateNotesPanel
            personId={personId}
            managedProfile={managedProfile}
            initialTotal={overview.private_notes.total}
          />
          <PrivateReflectionsPanel
            personId={personId}
            managedProfile={managedProfile}
            initialTotal={overview.private_reflections.total}
          />
        </div>
      </section>

      <ClusterCard
        eyebrow={t("app.workspace.clusterArchiveTitle")}
        title={t("app.workspace.clusterArchiveTitle")}
        description={t("app.workspace.clusterArchiveBody")}
      >
        <p className="mb-3 text-sm text-text">
          {overview.reports.total} {t("app.workspace.reportsTotalLabel")}
        </p>
        {overview.reports.latest ? (
          <div className="flex flex-wrap items-center gap-3">
            <p className="text-xs text-muted">
              {overview.reports.latest.report_type} · {formatDateTime(overview.reports.latest.created_at)}
            </p>
            <LinkButton href={`/reports/${overview.reports.latest.id}`} variant="secondary" size="sm">
              {t("app.workspace.reportsViewLatest")} <ArrowRight className="h-3.5 w-3.5" aria-hidden="true" />
            </LinkButton>
          </div>
        ) : (
          <p className="text-sm text-muted">{t("app.workspace.reportsEmpty")}</p>
        )}
        <LinkButton href="/reports" variant="ghost" size="sm" className="mt-3">
          {t("app.workspace.reportsViewAll")} <ArrowRight className="h-3.5 w-3.5" aria-hidden="true" />
        </LinkButton>
      </ClusterCard>
    </div>
  );
}

export default function WorkspaceHubPage() {
  const params = useParams<{ id: string }>();
  const personId = params.id;
  const { t } = useLocale();
  const overviewState = useAsync(() => api.myWorkspace.get(personId), [personId]);
  const peopleState = useAsync(() => api.people.list(), []);

  return (
    <AppShell>
      {(overviewState.status === "loading" || peopleState.status === "loading") && (
        <LoadingState label={t("app.workspace.loading")} />
      )}
      {overviewState.status === "error" && (
        <ErrorState error={overviewState.error} onRetry={overviewState.reload} title={t("app.workspace.errorTitle")} />
      )}
      {overviewState.status === "success" && peopleState.status === "success" && (
        <>
          {overviewState.data.person.id === personId ? (
            <div className="animate-rise-in">
              <WorkspaceHeader person={overviewState.data.person} people={peopleState.data} />
              <WorkspaceOverview personId={personId} overview={overviewState.data} />
            </div>
          ) : (
            <LoadingState label={t("app.workspace.loading")} />
          )}
        </>
      )}
    </AppShell>
  );
}
