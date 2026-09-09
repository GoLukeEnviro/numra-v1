"use client";

import { AppShell } from "@/components/layout/app-shell";
import { ComingSoonState } from "@/components/ui/states";
import { useLocale } from "@/i18n/context";

// V2 placeholder (PR-WEB-00): real Workspaces wiring (list/get/patch, consent,
// check-ins, tasks, roadmaps, api.workspaces.*) lands in later PRs. No fetch, no
// hook -- this route exists purely so the nav entry never 404s.
function WorkspacesContent() {
  const { t } = useLocale();
  return (
    <ComingSoonState title={t("app.workspaces.title")} description={t("app.workspaces.body")} />
  );
}

export default function WorkspacesPage() {
  return (
    <AppShell>
      <WorkspacesContent />
    </AppShell>
  );
}
