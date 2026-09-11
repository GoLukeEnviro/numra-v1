"use client";

import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { useParams } from "next/navigation";
import { AppShell } from "@/components/layout/app-shell";
import { LoadingState, ErrorState } from "@/components/ui/states";
import { RelationshipWorkspaceHeader } from "@/components/workspaces/relationship-workspace-header";
import { WorkspaceNavTabs } from "@/components/workspaces/workspace-nav-tabs";
import { RelationshipTypeSelector } from "@/components/workspaces/relationship-type-selector";
import { DualProfileGrid } from "@/components/workspaces/dual-profile-grid";
import { ConsentSummaryCard } from "@/components/workspaces/consent-summary-card";
import { FeatureStubCard } from "@/components/workspaces/feature-stub-card";
import { useLocale } from "@/i18n/context";
import { useAsync } from "@/lib/use-async";
import { useAuth } from "@/lib/auth-context";
import { api, ApiError, type WorkspaceOverviewOut } from "@/api/client";

function HubContent({ overview, workspaceId, checkinRoundOpen }: { overview: WorkspaceOverviewOut; workspaceId: string; checkinRoundOpen: boolean }) {
  const { t } = useLocale();
  const { user } = useAuth();
  const counterpart = overview.dual_profile.find((m) => m.user_id !== user?.id);
  const counterpartName = counterpart?.display_name ?? "";

  return (
    <div className="animate-rise-in">
      <RelationshipWorkspaceHeader
        workspaceId={workspaceId}
        workspace={overview.workspace}
        counterpartName={counterpartName}
      />
      <WorkspaceNavTabs workspaceId={workspaceId} />
      <div className="flex flex-col gap-8">
        <RelationshipTypeSelector workspaceId={workspaceId} workspace={overview.workspace} checkinRoundOpen={checkinRoundOpen} />
        <DualProfileGrid workspaceId={workspaceId} members={overview.dual_profile} />
        <ConsentSummaryCard workspaceId={workspaceId} counterpartName={counterpartName} />
        <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
          <section>
            <h2 className="mb-2 text-xs font-semibold uppercase tracking-wider text-bronze">
              {t("app.dynamics.hubLinkTitle")}
            </h2>
            <Link
              href={`/workspaces/${workspaceId}/dynamics`}
              className="flex items-center justify-between gap-3 rounded-xl border border-white/10 bg-surface p-6 transition-colors hover:border-gold/50"
            >
              <span>
                <span className="block font-serif text-lg text-ivory">
                  {t("app.dynamics.hubLinkTitle")}
                </span>
                <span className="mt-1 block max-w-md text-sm text-muted">
                  {t("app.dynamics.hubLinkBody")}
                </span>
              </span>
              <ArrowRight className="h-5 w-5 shrink-0 text-gold" aria-hidden="true" />
            </Link>
          </section>
          <section>
            <h2 className="mb-2 text-xs font-semibold uppercase tracking-wider text-bronze">
              {t("app.relationshipWorkspace.stubCheckinsTitle")}
            </h2>
            <Link
              href={`/workspaces/${workspaceId}/checkins`}
              className="flex items-center justify-between gap-3 rounded-xl border border-white/10 bg-surface p-6 transition-colors hover:border-gold/50"
            >
              <span>
                <span className="block font-serif text-lg text-ivory">{t("app.relationshipWorkspace.stubCheckinsTitle")}</span>
                <span className="mt-1 block max-w-md text-sm text-muted">{t("app.checkins.hubBody")}</span>
              </span>
              <ArrowRight className="h-5 w-5 shrink-0 text-gold" aria-hidden="true" />
            </Link>
          </section>
          <section>
            <h2 className="mb-2 text-xs font-semibold uppercase tracking-wider text-bronze">{t("app.relationshipWorkspace.stubTasksTitle")}</h2>
            <Link href={`/workspaces/${workspaceId}/tasks`} className="flex items-center justify-between gap-3 rounded-xl border border-white/10 bg-surface p-6 transition-colors hover:border-gold/50">
              <span><span className="block font-serif text-lg text-ivory">{t("app.relationshipWorkspace.stubTasksTitle")}</span><span className="mt-1 block max-w-md text-sm text-muted">{t("app.tasks.hubBody")}</span></span>
              <ArrowRight className="h-5 w-5 shrink-0 text-gold" aria-hidden="true" />
            </Link>
          </section>
          <FeatureStubCard
            eyebrow={t("app.relationshipWorkspace.stubRoadmapTitle")}
            title={t("app.relationshipWorkspace.stubRoadmapTitle")}
            description={t("app.relationshipWorkspace.stubRoadmapBody")}
          />
          <FeatureStubCard
            eyebrow={t("app.relationshipWorkspace.stubReflectionTitle")}
            title={t("app.relationshipWorkspace.stubReflectionTitle")}
            description={t("app.relationshipWorkspace.stubReflectionBody")}
          />
          <FeatureStubCard
            eyebrow={t("app.relationshipWorkspace.stubCopilotTitle")}
            title={t("app.relationshipWorkspace.stubCopilotTitle")}
            description={t("app.relationshipWorkspace.stubCopilotBody")}
          />
        </div>
      </div>
    </div>
  );
}

export default function RelationshipWorkspaceHubPage() {
  const params = useParams<{ id: string }>();
  const workspaceId = params.id;
  const { t } = useLocale();
  const overviewState = useAsync(async () => {
    const overview = await api.workspaces.get(workspaceId);
    const checkinRoundOpen = await api.workspaces.checkins.current(workspaceId)
      .then((round) => round?.status === "AWAITING_SUBMISSIONS")
      .catch((error: unknown) => {
        if (error instanceof ApiError && ["V2_DISABLED", "V2_PHASE_DISABLED"].includes(error.code)) return false;
        throw error;
      });
    return { overview, checkinRoundOpen };
  }, [workspaceId]);

  return (
    <AppShell>
      {overviewState.status === "loading" && <LoadingState label={t("app.relationshipWorkspace.headerLoading")} />}
      {overviewState.status === "error" && (
        <ErrorState error={overviewState.error} onRetry={overviewState.reload} />
      )}
      {overviewState.status === "success" &&
        (overviewState.data.overview.workspace.id === workspaceId ? (
          <HubContent overview={overviewState.data.overview} workspaceId={workspaceId} checkinRoundOpen={overviewState.data.checkinRoundOpen} />
        ) : (
          <LoadingState label={t("app.relationshipWorkspace.headerLoading")} />
        ))}
    </AppShell>
  );
}
