"use client";
import { useParams } from "next/navigation";
import { api } from "@/api/client";
import { AppShell } from "@/components/layout/app-shell";
import { ErrorState, LoadingState, PhaseDisabledState, isPhaseDisabledError } from "@/components/ui/states";
import { loadAll, WorkspaceRoadmapsContent } from "@/components/workspaces/roadmaps/workspace-roadmaps-content";
import { useAsync } from "@/lib/use-async";
import { useLocale } from "@/i18n/context";

function Body({ id }: { id: string }) {
  const { t } = useLocale();
  const state = useAsync(async () => {
    const [overview, roadmaps, tasks] = await Promise.all([api.workspaces.get(id), loadAll((p) => api.workspaces.roadmaps.list(id, p)), loadAll((p) => api.workspaces.tasks.list(id, p))]);
    const entries = await Promise.all(roadmaps.map(async (roadmap) => ({ roadmap, milestones: await api.workspaces.roadmaps.milestones.list(id, roadmap.id) })));
    return { overview, entries, tasks };
  }, [id]);
  if (state.status === "loading") return <LoadingState label={t("app.tasks.loading")} />;
  if (state.status === "error") return isPhaseDisabledError(state.error) ? <PhaseDisabledState code={state.error.code} title={t("app.roadmaps.disabled")} description={t("app.roadmaps.disabledBody")} /> : <ErrorState error={state.error} onRetry={state.reload} />;
  return <WorkspaceRoadmapsContent workspaceId={id} {...state.data} />;
}
export default function Page() { const { id } = useParams<{ id: string }>(); return <AppShell><Body key={id} id={id} /></AppShell>; }
