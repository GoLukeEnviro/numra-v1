"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import { api } from "@/api/client";
import { AppShell } from "@/components/layout/app-shell";
import { ErrorState, LoadingState, PhaseDisabledState, isPhaseDisabledError, type PhaseErrorCode } from "@/components/ui/states";
import { WorkspaceCopilotContent } from "@/components/workspaces/copilot/workspace-copilot-content";
import { useLocale } from "@/i18n/context";
import { useAsync } from "@/lib/use-async";

function Body({ id }: { id: string }) {
  const { t } = useLocale();
  const [copilotDisabledCode, setCopilotDisabledCode] = useState<PhaseErrorCode | null>(null);
  const state = useAsync(() => api.workspaces.get(id), [id]);
  if (state.status === "loading") return <LoadingState label={t("app.copilot.indexLoading")} />;
  if (state.status === "error") return isPhaseDisabledError(state.error)
    ? <PhaseDisabledState code={state.error.code} title={t("app.copilot.disabled")} description={t("app.copilot.disabledBody")} />
    : <ErrorState error={state.error} onRetry={state.reload} />;
  if (copilotDisabledCode) return <PhaseDisabledState code={copilotDisabledCode} title={t("app.copilot.disabled")} description={t("app.copilot.disabledBody")} />;
  return <WorkspaceCopilotContent workspaceId={id} overview={state.data} onPhaseDisabled={setCopilotDisabledCode} />;
}

export default function WorkspaceCopilotPage() {
  const { id } = useParams<{ id: string }>();
  return <AppShell><Body key={id} id={id} /></AppShell>;
}
