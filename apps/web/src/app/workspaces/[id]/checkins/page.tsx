"use client";

import { useParams } from "next/navigation";
import { api, ApiError, type CheckinSummaryOut } from "@/api/client";
import { AppShell } from "@/components/layout/app-shell";
import { ErrorState, LoadingState, PhaseDisabledState, isPhaseDisabledError } from "@/components/ui/states";
import { CheckinsContent } from "@/components/workspaces/checkins/checkins-content";
import { useLocale } from "@/i18n/context";
import { useAsync } from "@/lib/use-async";

function CheckinsPageBody({ workspaceId }: { workspaceId: string }) {
  const { t } = useLocale();
  const state = useAsync(async () => {
    const overview = await api.workspaces.get(workspaceId);
    const loadHistory = async () => {
      const all: CheckinSummaryOut[] = [];
      const limit = 200;
      for (let offset = 0; ; offset += limit) {
        const page = await api.workspaces.checkins.list(workspaceId, { limit, offset });
        all.push(...page);
        if (page.length < limit) return all;
      }
    };
    const [current, history, template] = await Promise.all([
      api.workspaces.checkins.current(workspaceId),
      loadHistory(),
      api.workspaces.checkinTemplate.get(workspaceId).catch((error: unknown) => {
        if (overview.workspace.status === "DISSOLVED" && error instanceof ApiError && error.status === 404) return null;
        throw error;
      }),
    ]);
    return { overview, current, history, template };
  }, [workspaceId]);

  if (state.status === "loading") return <LoadingState label={t("app.checkins.loading")} />;
  if (state.status === "error") {
    return isPhaseDisabledError(state.error) ? (
      <PhaseDisabledState code={state.error.code} title={t("app.checkins.disabledTitle")} description={t("app.checkins.disabledBody")} />
    ) : (
      <ErrorState error={state.error} onRetry={state.reload} title={t("app.checkins.loadError")} />
    );
  }
  if (state.data.overview.workspace.id !== workspaceId) return <LoadingState label={t("app.checkins.loading")} />;
  return <CheckinsContent workspaceId={workspaceId} {...state.data} onReload={state.reload} />;
}

export default function WorkspaceCheckinsPage() {
  const params = useParams<{ id: string }>();
  return <AppShell><CheckinsPageBody workspaceId={params.id} /></AppShell>;
}
