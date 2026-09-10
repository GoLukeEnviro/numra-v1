"use client";

import { useParams } from "next/navigation";
import { AppShell } from "@/components/layout/app-shell";
import {
  LoadingState,
  ErrorState,
  PhaseDisabledState,
  isPhaseDisabledError,
} from "@/components/ui/states";
import { DynamicsContent } from "@/components/workspaces/dynamics/dynamics-content";
import { useLocale } from "@/i18n/context";
import { useAsync } from "@/lib/use-async";
import { api } from "@/api/client";

function DynamicsPageBody({ workspaceId }: { workspaceId: string }) {
  const { t } = useLocale();
  const overviewState = useAsync(() => api.workspaces.get(workspaceId), [workspaceId]);

  if (overviewState.status === "loading") {
    return <LoadingState label={t("app.relationshipWorkspace.headerLoading")} />;
  }
  if (overviewState.status === "error") {
    return isPhaseDisabledError(overviewState.error) ? (
      <PhaseDisabledState
        code={overviewState.error.code}
        title={t("app.dynamics.gate.workspaceDissolvedTitle")}
        description={t("app.dynamics.gate.workspaceDissolvedBody")}
      />
    ) : (
      <ErrorState error={overviewState.error} onRetry={overviewState.reload} />
    );
  }
  // State isolation: keep Loading until the response is for the route's workspace.
  if (overviewState.data.workspace.id !== workspaceId) {
    return <LoadingState label={t("app.relationshipWorkspace.headerLoading")} />;
  }
  return <DynamicsContent overview={overviewState.data} workspaceId={workspaceId} />;
}

export default function WorkspaceDynamicsPage() {
  const params = useParams<{ id: string }>();
  return (
    <AppShell>
      <DynamicsPageBody workspaceId={params.id} />
    </AppShell>
  );
}
