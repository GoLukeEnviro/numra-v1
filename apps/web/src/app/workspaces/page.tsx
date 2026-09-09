"use client";

import Link from "next/link";
import { AppShell } from "@/components/layout/app-shell";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { LinkButton } from "@/components/ui/link-button";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/states";
import { useLocale } from "@/i18n/context";
import { useAsync } from "@/lib/use-async";
import { buildCounterpartNameMap } from "@/lib/identity";
import { api, type RelationshipType, type WorkspaceSummaryOut } from "@/api/client";
import type { MessageKey } from "@/i18n/catalog";

const RELATIONSHIP_TYPE_KEYS: Record<RelationshipType, MessageKey> = {
  PARTNER: "app.relationshipWorkspace.typePartner",
  DATING: "app.relationshipWorkspace.typeDating",
  FRIENDSHIP: "app.relationshipWorkspace.typeFriendship",
  FAMILY: "app.relationshipWorkspace.typeFamily",
  SIBLINGS: "app.relationshipWorkspace.typeSiblings",
  PARENT_CHILD: "app.relationshipWorkspace.typeParentChild",
  WORK: "app.relationshipWorkspace.typeWork",
  OTHER: "app.relationshipWorkspace.typeOther",
};

function WorkspaceRow({
  workspace,
  counterpartName,
  dissolved,
}: {
  workspace: WorkspaceSummaryOut;
  counterpartName: string;
  dissolved: boolean;
}) {
  const { t } = useLocale();
  return (
    <Link
      href={`/workspaces/${workspace.id}`}
      className={`flex flex-wrap items-center justify-between gap-3 border-b border-white/5 py-3 last:border-0 hover:bg-white/[0.03] ${dissolved ? "opacity-60" : ""}`}
    >
      <span className="truncate text-sm font-medium text-ivory">{counterpartName}</span>
      {workspace.relationship_type ? (
        <Badge variant="neutral">{t(RELATIONSHIP_TYPE_KEYS[workspace.relationship_type])}</Badge>
      ) : (
        <span className="text-xs text-muted">{t("app.relationshipWorkspace.listTypeUnset")}</span>
      )}
    </Link>
  );
}

function WorkspacesContent() {
  const { t } = useLocale();
  const workspacesState = useAsync(() => api.workspaces.list(), []);
  const connectionsState = useAsync(() => api.connections.list(), []);

  if (workspacesState.status === "loading" || connectionsState.status === "loading") {
    return <LoadingState label={t("app.relationshipWorkspace.listLoading")} />;
  }
  if (workspacesState.status === "error") {
    return (
      <ErrorState
        error={workspacesState.error}
        onRetry={workspacesState.reload}
        title={t("app.relationshipWorkspace.listLoadError")}
      />
    );
  }
  if (connectionsState.status === "error") {
    return (
      <ErrorState
        error={connectionsState.error}
        onRetry={connectionsState.reload}
        title={t("app.relationshipWorkspace.listLoadError")}
      />
    );
  }

  const workspaces = workspacesState.data;
  const counterpartNameById = buildCounterpartNameMap(connectionsState.data, workspaces);
  const fallbackName = t("app.relationshipWorkspace.listFallbackName");
  const nameFor = (id: string) => counterpartNameById.get(id) ?? fallbackName;

  const active = workspaces.filter((w) => w.status === "ACTIVE");
  const dissolved = workspaces
    .filter((w) => w.status === "DISSOLVED")
    .sort((a, b) => (b.dissolved_at ?? "").localeCompare(a.dissolved_at ?? ""));

  if (workspaces.length === 0) {
    return (
      <EmptyState
        title={t("app.relationshipWorkspace.listEmptyTitle")}
        description={t("app.relationshipWorkspace.listEmptyBody")}
        action={
          <LinkButton variant="secondary" href="/connections">
            {t("app.relationshipWorkspace.listEmptyCta")}
          </LinkButton>
        }
      />
    );
  }

  return (
    <div className="animate-rise-in flex flex-col gap-6">
      <header>
        <h1 className="font-serif text-3xl text-ivory">{t("app.workspaces.title")}</h1>
        <p className="mt-1 text-sm text-muted">{t("app.workspaces.body")}</p>
      </header>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">{t("app.relationshipWorkspace.listActiveTitle")}</CardTitle>
        </CardHeader>
        <CardContent>
          {active.length === 0 ? (
            <EmptyState title={t("app.relationshipWorkspace.listEmptyTitle")} />
          ) : (
            active.map((w) => (
              <WorkspaceRow key={w.id} workspace={w} counterpartName={nameFor(w.id)} dissolved={false} />
            ))
          )}
        </CardContent>
      </Card>

      {dissolved.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">{t("app.relationshipWorkspace.listDissolvedTitle")}</CardTitle>
          </CardHeader>
          <CardContent>
            {dissolved.map((w) => (
              <WorkspaceRow key={w.id} workspace={w} counterpartName={nameFor(w.id)} dissolved />
            ))}
          </CardContent>
        </Card>
      )}
    </div>
  );
}

export default function WorkspacesPage() {
  return (
    <AppShell>
      <WorkspacesContent />
    </AppShell>
  );
}
