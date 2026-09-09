"use client";

import { AppShell } from "@/components/layout/app-shell";
import { ComingSoonState } from "@/components/ui/states";
import { useLocale } from "@/i18n/context";

// V2 placeholder (PR-WEB-00): real Copilot wiring (workspace-scoped chat threads,
// api.workspaces.copilot.threads.*) lands in a later PR. No fetch, no hook -- this
// route exists purely so the nav entry never 404s.
function CopilotContent() {
  const { t } = useLocale();
  return <ComingSoonState title={t("app.copilot.title")} description={t("app.copilot.body")} />;
}

export default function CopilotPage() {
  return (
    <AppShell>
      <CopilotContent />
    </AppShell>
  );
}
