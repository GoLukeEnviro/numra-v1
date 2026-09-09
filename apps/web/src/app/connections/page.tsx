"use client";

import { AppShell } from "@/components/layout/app-shell";
import { ComingSoonState } from "@/components/ui/states";
import { useLocale } from "@/i18n/context";

// V2 placeholder (PR-WEB-00): real Connections wiring (invite/accept/decline/
// revoke/dissolve, api.connections.*) lands in a later PR. No fetch, no hook --
// this route exists purely so the nav entry never 404s.
function ConnectionsContent() {
  const { t } = useLocale();
  return (
    <ComingSoonState title={t("app.connections.title")} description={t("app.connections.body")} />
  );
}

export default function ConnectionsPage() {
  return (
    <AppShell>
      <ConnectionsContent />
    </AppShell>
  );
}
