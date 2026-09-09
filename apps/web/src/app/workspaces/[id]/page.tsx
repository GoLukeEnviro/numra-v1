"use client";

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
import { api, type WorkspaceOverviewOut } from "@/api/client";

function HubContent({ overview, workspaceId }: { overview: WorkspaceOverviewOut; workspaceId: string }) {
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
        <RelationshipTypeSelector workspaceId={workspaceId} workspace={overview.workspace} />
        <DualProfileGrid workspaceId={workspaceId} members={overview.dual_profile} />
        <ConsentSummaryCard workspaceId={workspaceId} counterpartName={counterpartName} />
        <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
          <FeatureStubCard
            eyebrow={t("app.relationshipWorkspace.stubDynamicsTitle")}
            title={t("app.relationshipWorkspace.stubDynamicsTitle")}
            description={t("app.relationshipWorkspace.stubDynamicsBody")}
          />
          <FeatureStubCard
            eyebrow={t("app.relationshipWorkspace.stubCheckinsTitle")}
            title={t("app.relationshipWorkspace.stubCheckinsTitle")}
            description={t("app.relationshipWorkspace.stubCheckinsBody")}
          />
          <FeatureStubCard
            eyebrow={t("app.relationshipWorkspace.stubTasksTitle")}
            title={t("app.relationshipWorkspace.stubTasksTitle")}
            description={t("app.relationshipWorkspace.stubTasksBody")}
          />
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
  const overviewState = useAsync(() => api.workspaces.get(workspaceId), [workspaceId]);

  return (
    <AppShell>
      {overviewState.status === "loading" && <LoadingState label={t("app.relationshipWorkspace.headerLoading")} />}
      {overviewState.status === "error" && (
        <ErrorState error={overviewState.error} onRetry={overviewState.reload} />
      )}
      {overviewState.status === "success" &&
        (overviewState.data.workspace.id === workspaceId ? (
          <HubContent overview={overviewState.data} workspaceId={workspaceId} />
        ) : (
          <LoadingState label={t("app.relationshipWorkspace.headerLoading")} />
        ))}
    </AppShell>
  );
}
