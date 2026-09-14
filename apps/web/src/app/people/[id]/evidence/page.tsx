"use client";

import { useParams } from "next/navigation";
import { api } from "@/api/client";
import { AppShell } from "@/components/layout/app-shell";
import { EvidenceLayerContent } from "@/components/people/evidence/evidence-layer-content";
import { ErrorState, LoadingState } from "@/components/ui/states";
import { useLocale } from "@/i18n/context";
import { personDisplayName } from "@/lib/identity";
import { useAsync } from "@/lib/use-async";

function Body({ personId }: { personId: string }) {
  const { t } = useLocale();
  const state = useAsync(() => api.people.get(personId), [personId]);
  if (state.status === "loading") return <LoadingState label={t("app.evidence.loading")} />;
  if (state.status === "error") return <ErrorState error={state.error} onRetry={state.reload} />;
  return <EvidenceLayerContent personId={personId} personName={personDisplayName(state.data)} />;
}

export default function EvidencePage() {
  const { id } = useParams<{ id: string }>();
  return <AppShell><Body key={id} personId={id} /></AppShell>;
}
