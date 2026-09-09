"use client";

import { useRouter } from "next/navigation";
import { NumericWheel } from "@/components/layout/numeric-wheel";
import { Badge } from "@/components/ui/badge";
import { WorkspaceSwitcher } from "@/components/workspaces/workspace-switcher";
import { workspacesToWorkspaceOptions } from "@/components/workspaces/workspace-switcher-relationship";
import { useLocale } from "@/i18n/context";
import { useAsync } from "@/lib/use-async";
import { useAuth } from "@/lib/auth-context";
import { buildCounterpartNameMap } from "@/lib/identity";
import { formatDateTime } from "@/lib/utils";
import { api, type WorkspaceOut } from "@/api/client";

export interface RelationshipWorkspaceHeaderProps {
  workspaceId: string;
  workspace: WorkspaceOut;
  counterpartName: string;
}

/** Header for the Relationship Workspace hub -- counterpart name as title, ACTIVE/
 *  DISSOLVED status badge, and a WorkspaceSwitcher to jump to another relationship
 *  workspace. Own `useAsync(api.workspaces.list)` call (no prop-drilling from the
 *  list page), same pattern as the Personal Workspace's `WorkspaceHeader`. */
export function RelationshipWorkspaceHeader({
  workspaceId,
  workspace,
  counterpartName,
}: RelationshipWorkspaceHeaderProps) {
  const router = useRouter();
  const { t } = useLocale();
  const workspacesState = useAsync(() => api.workspaces.list(), []);
  const connectionsState = useAsync(() => api.connections.list(), []);

  const workspaces = workspacesState.status === "success" ? workspacesState.data : [];
  const connections = connectionsState.status === "success" ? connectionsState.data : [];
  const counterpartNameById = buildCounterpartNameMap(connections, workspaces);
  const options = workspacesToWorkspaceOptions(
    workspaces,
    counterpartNameById,
    t("app.relationshipWorkspace.listFallbackName"),
  );

  return (
    <header className="sacred-wheel-bg-left relative mb-8 overflow-hidden rounded-xl border border-white/10 bg-surface p-6 shadow-elevated sm:p-8">
      <NumericWheel className="pointer-events-none absolute -right-16 -top-20 h-56 w-56 opacity-[0.12]" />
      <div className="relative flex flex-wrap items-end justify-between gap-6">
        <div className="min-w-0">
          <p className="mb-2 text-xs uppercase tracking-wider text-bronze">
            {t("app.relationshipWorkspace.headerEyebrow")}
          </p>
          <div className="flex flex-wrap items-center gap-3">
            <h1 className="font-serif text-3xl text-ivory sm:text-4xl">{counterpartName}</h1>
            {workspace.status === "ACTIVE" ? (
              <Badge variant="success">{t("app.relationshipWorkspace.statusActive")}</Badge>
            ) : (
              <Badge variant="neutral">
                {t("app.relationshipWorkspace.statusDissolvedPrefix")} {formatDateTime(workspace.dissolved_at)}
              </Badge>
            )}
          </div>
        </div>
        {workspaces.length > 1 && (
          <WorkspaceSwitcher
            className="w-full sm:w-72"
            options={options}
            activeId={workspaceId}
            onSelect={(id) => router.push(`/workspaces/${id}`)}
          />
        )}
      </div>
    </header>
  );
}
