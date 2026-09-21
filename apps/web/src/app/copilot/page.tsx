"use client";

import { useState } from "react";
import Link from "next/link";
import { Sparkles } from "lucide-react";
import { api } from "@/api/client";
import { AppShell } from "@/components/layout/app-shell";
import { PersonalCopilotContent } from "@/components/copilot/personal-copilot-content";
import { Card, CardContent } from "@/components/ui/card";
import { LinkButton } from "@/components/ui/link-button";
import { EmptyState, ErrorState, LoadingState, PhaseDisabledState, isPhaseDisabledError, type PhaseErrorCode } from "@/components/ui/states";
import { useLocale } from "@/i18n/context";
import { buildCounterpartNameMap } from "@/lib/identity";
import { useAsync } from "@/lib/use-async";

/**
 * PWA-06 / #123 -- `/copilot` is the personal surface first and the relationship
 * index second. Before this change the page listed only ACTIVE relationship
 * workspaces, so a user without a connection had no personal copilot at all even
 * though the API supports one (`/v1/me/copilot`). The relationship list stays, so
 * nothing that worked before becomes unreachable -- it just moved below the personal
 * conversation. The personal surface renders nothing about relationships, and the
 * relationship list renders nothing about personal threads.
 */
function RelationshipWorkspaceIndex() {
  const { t } = useLocale();
  const workspaces = useAsync(() => api.workspaces.list(), []);
  const connections = useAsync(() => api.connections.list(), []);
  if (workspaces.status === "loading" || connections.status === "loading") return <LoadingState label={t("app.copilot.indexLoading")} />;
  if (workspaces.status === "error") return <ErrorState error={workspaces.error} onRetry={workspaces.reload} />;
  if (connections.status === "error") return <ErrorState error={connections.error} onRetry={connections.reload} />;
  const active = workspaces.data.filter((workspace) => workspace.status === "ACTIVE");
  if (!active.length) return <EmptyState title={t("app.copilot.indexEmptyTitle")} description={t("app.copilot.indexEmptyBody")} action={<LinkButton variant="secondary" href="/connections">{t("app.relationshipWorkspace.listEmptyCta")}</LinkButton>} />;
  const names = buildCounterpartNameMap(connections.data, workspaces.data);
  return <div className="grid gap-4 md:grid-cols-2">{active.map((workspace) => <Link key={workspace.id} href={`/workspaces/${workspace.id}/copilot`}>
    <Card className="h-full transition-colors hover:border-gold/40"><CardContent className="flex items-center gap-4 p-5"><Sparkles className="h-5 w-5 text-gold" /><div><p className="font-medium text-ivory">{names.get(workspace.id) ?? t("app.relationshipWorkspace.listFallbackName")}</p><p className="mt-1 text-sm text-muted">{t("app.copilot.indexOpen")}</p></div></CardContent></Card>
  </Link>)}</div>;
}

function CopilotContent() {
  const { t } = useLocale();
  const [personalDisabledCode, setPersonalDisabledCode] = useState<PhaseErrorCode | null>(null);
  return <div className="animate-rise-in">
    <header className="mb-6 max-w-reading">
      <h1 className="font-serif text-3xl text-ivory">{t("nav.copilot")}</h1>
      <p className="mt-2 text-sm text-muted">{t("app.copilot.indexIntro")}</p>
    </header>
    {personalDisabledCode
      ? <PhaseDisabledState code={personalDisabledCode} title={t("app.copilot.disabled")} description={t("app.copilot.disabledBody")} />
      : <PersonalCopilotContent onPhaseDisabled={setPersonalDisabledCode} />}
    <section aria-labelledby="relationship-copilot-index-heading">
      <h2 id="relationship-copilot-index-heading" className="mb-4 font-serif text-2xl text-ivory">{t("app.copilot.indexWorkspacesTitle")}</h2>
      <RelationshipWorkspaceIndex />
    </section>
  </div>;
}

export default function CopilotPage() {
  return (
    <AppShell>
      <CopilotContent />
    </AppShell>
  );
}
