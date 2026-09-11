"use client";

import Link from "next/link";
import { Sparkles } from "lucide-react";
import { api } from "@/api/client";
import { AppShell } from "@/components/layout/app-shell";
import { Card, CardContent } from "@/components/ui/card";
import { LinkButton } from "@/components/ui/link-button";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/states";
import { useLocale } from "@/i18n/context";
import { buildCounterpartNameMap } from "@/lib/identity";
import { useAsync } from "@/lib/use-async";

function CopilotContent() {
  const { t } = useLocale();
  const workspaces = useAsync(() => api.workspaces.list(), []);
  const connections = useAsync(() => api.connections.list(), []);
  if (workspaces.status === "loading" || connections.status === "loading") return <LoadingState label={t("app.copilot.indexLoading")} />;
  if (workspaces.status === "error") return <ErrorState error={workspaces.error} onRetry={workspaces.reload} />;
  if (connections.status === "error") return <ErrorState error={connections.error} onRetry={connections.reload} />;
  const active = workspaces.data.filter((workspace) => workspace.status === "ACTIVE");
  if (!active.length) return <EmptyState title={t("app.copilot.indexEmptyTitle")} description={t("app.copilot.indexEmptyBody")} action={<LinkButton variant="secondary" href="/connections">{t("app.relationshipWorkspace.listEmptyCta")}</LinkButton>} />;
  const names = buildCounterpartNameMap(connections.data, workspaces.data);
  return <div className="animate-rise-in space-y-6">
    <header><h1 className="font-serif text-3xl text-ivory">{t("nav.copilot")}</h1><p className="mt-2 text-sm text-muted">{t("app.copilot.indexIntro")}</p></header>
    <div className="grid gap-4 md:grid-cols-2">{active.map((workspace) => <Link key={workspace.id} href={`/workspaces/${workspace.id}/copilot`}>
      <Card className="h-full transition-colors hover:border-gold/40"><CardContent className="flex items-center gap-4 p-5"><Sparkles className="h-5 w-5 text-gold" /><div><p className="font-medium text-ivory">{names.get(workspace.id) ?? t("app.relationshipWorkspace.listFallbackName")}</p><p className="mt-1 text-sm text-muted">{t("app.copilot.indexOpen")}</p></div></CardContent></Card>
    </Link>)}</div>
  </div>;
}

export default function CopilotPage() {
  return (
    <AppShell>
      <CopilotContent />
    </AppShell>
  );
}
