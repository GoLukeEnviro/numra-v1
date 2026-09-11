"use client";

import { useParams } from "next/navigation";
import { api, type WorkspaceTaskOut } from "@/api/client";
import { AppShell } from "@/components/layout/app-shell";
import { ErrorState, LoadingState, PhaseDisabledState, isPhaseDisabledError } from "@/components/ui/states";
import { WorkspaceTasksContent } from "@/components/workspaces/tasks/workspace-tasks-content";
import { useLocale } from "@/i18n/context";
import { useAsync } from "@/lib/use-async";

function TasksPageBody({ workspaceId }: { workspaceId: string }) {
  const { t } = useLocale();
  const state = useAsync(async () => {
    const overview = await api.workspaces.get(workspaceId);
    const tasks: WorkspaceTaskOut[] = [];
    const limit = 200;
    for (let offset = 0; ; offset += limit) {
      const page = await api.workspaces.tasks.list(workspaceId, { limit, offset });
      tasks.push(...page);
      if (page.length < limit) break;
    }
    return { overview, tasks };
  }, [workspaceId]);

  if (state.status === "loading") return <LoadingState label={t("app.tasks.loading")} />;
  if (state.status === "error") {
    return isPhaseDisabledError(state.error) ? (
      <PhaseDisabledState code={state.error.code} title={t("app.tasks.disabledTitle")} description={t("app.tasks.disabledBody")} />
    ) : (
      <ErrorState error={state.error} onRetry={state.reload} title={t("app.tasks.loadError")} />
    );
  }
  if (state.data.overview.workspace.id !== workspaceId) return <LoadingState label={t("app.tasks.loading")} />;
  return <WorkspaceTasksContent workspaceId={workspaceId} {...state.data} />;
}

export default function WorkspaceTasksPage() {
  const params = useParams<{ id: string }>();
  return <AppShell><TasksPageBody workspaceId={params.id} /></AppShell>;
}
