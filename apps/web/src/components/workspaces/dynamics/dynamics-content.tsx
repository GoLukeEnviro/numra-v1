"use client";

import { RelationshipWorkspaceHeader } from "@/components/workspaces/relationship-workspace-header";
import { WorkspaceNavTabs } from "@/components/workspaces/workspace-nav-tabs";
import { PhaseDisabledState } from "@/components/ui/states";
import { AnalysisSection } from "@/components/workspaces/dynamics/analysis-section";
import { useLocale } from "@/i18n/context";
import { useAuth } from "@/lib/auth-context";
import type { WorkspaceOverviewOut } from "@/api/client";

/**
 * The `/workspaces/[id]/dynamics` body: workspace header + nav, then the two
 * independent, stacked analysis sections (Relationship first, then Shadow). A
 * DISSOLVED workspace replaces both sections with one calm full-width gate.
 */
export function DynamicsContent({
  overview,
  workspaceId,
}: {
  overview: WorkspaceOverviewOut;
  workspaceId: string;
}) {
  const { t } = useLocale();
  const { user } = useAuth();
  const counterpart = overview.dual_profile.find((m) => m.user_id !== user?.id);
  const counterpartName = counterpart?.display_name ?? "";
  const dissolved = overview.workspace.status === "DISSOLVED";

  return (
    <div className="animate-rise-in">
      <RelationshipWorkspaceHeader
        workspaceId={workspaceId}
        workspace={overview.workspace}
        counterpartName={counterpartName}
      />
      <WorkspaceNavTabs workspaceId={workspaceId} />

      <div className="mb-6">
        <h1 className="font-serif text-3xl text-ivory">{t("app.dynamics.pageTitle")}</h1>
        <p className="mt-2 max-w-reading text-sm text-muted">{t("app.dynamics.pageIntro")}</p>
      </div>

      {dissolved ? (
        <PhaseDisabledState
          code="WORKSPACE_DISSOLVED"
          title={t("app.dynamics.gate.workspaceDissolvedTitle")}
          description={t("app.dynamics.gate.workspaceDissolvedBody")}
        />
      ) : (
        <div className="flex flex-col gap-12">
          <AnalysisSection workspaceId={workspaceId} kind="relationship" />
          <AnalysisSection workspaceId={workspaceId} kind="shadow" />
        </div>
      )}
    </div>
  );
}
