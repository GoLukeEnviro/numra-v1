"use client";
import { useParams } from "next/navigation";
import { api } from "@/api/client";
import { AppShell } from "@/components/layout/app-shell";
import { ErrorState, LoadingState, PhaseDisabledState, isPhaseDisabledError } from "@/components/ui/states";
import { loadAll } from "@/components/workspaces/roadmaps/workspace-roadmaps-content";
import { WorkspaceReflectionsContent } from "@/components/workspaces/roadmaps/workspace-reflections-content";
import { useAsync } from "@/lib/use-async";
import { useLocale } from "@/i18n/context";
function Body({ id }: { id: string }) {
  const { t } = useLocale();
  const state = useAsync(async () => {
    const [overview, reflections] = await Promise.all([api.workspaces.get(id), loadAll((p) => api.workspaces.sharedReflections.list(id, p))]);
    return { overview, reflections };
  }, [id]);
  if (state.status === "loading") return <LoadingState label={t("app.tasks.loading")} />;
  if (state.status === "error") return isPhaseDisabledError(state.error) ? <PhaseDisabledState code={state.error.code} title={t("app.reflections.disabled")} description={t("app.reflections.disabledBody")} /> : <ErrorState error={state.error} onRetry={state.reload} />;
  return <WorkspaceReflectionsContent workspaceId={id} {...state.data} />;
}
export default function Page() { const { id } = useParams<{ id: string }>(); return <AppShell><Body key={id} id={id} /></AppShell>; }
