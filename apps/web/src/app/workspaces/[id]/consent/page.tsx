"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import { AppShell } from "@/components/layout/app-shell";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ErrorState, LoadingState } from "@/components/ui/states";
import { useLocale } from "@/i18n/context";
import { useAsync } from "@/lib/use-async";
import { useAuth } from "@/lib/auth-context";
import { cn } from "@/lib/utils";
import { api, type ConsentGrantOut, type ConsentScope, type WorkspaceConsentOut } from "@/api/client";
import type { MessageKey } from "@/i18n/catalog";

const DEFAULT_SCOPES: ConsentScope[] = ["CORE_NUMEROLOGY", "RELATIONSHIP_INSIGHTS", "CURRENT_TIMING"];
const EXTENDED_SCOPES: ConsentScope[] = [
  "PRIVATE_JOURNAL",
  "PRIVATE_TASKS",
  "PRIVATE_COPILOT",
  "OTHER_RELATIONSHIPS",
  "LIFE_TRACKING",
];

const SCOPE_LABEL_KEYS: Record<ConsentScope, MessageKey> = {
  CORE_NUMEROLOGY: "app.consent.scopeCoreNumerology",
  RELATIONSHIP_INSIGHTS: "app.consent.scopeRelationshipInsights",
  CURRENT_TIMING: "app.consent.scopeCurrentTiming",
  PRIVATE_JOURNAL: "app.consent.scopePrivateJournal",
  PRIVATE_TASKS: "app.consent.scopePrivateTasks",
  PRIVATE_COPILOT: "app.consent.scopePrivateCopilot",
  OTHER_RELATIONSHIPS: "app.consent.scopeOtherRelationships",
  LIFE_TRACKING: "app.consent.scopeLifeTracking",
};

function isGranted(grants: ConsentGrantOut[], scope: ConsentScope): boolean {
  return grants.some((g) => g.scope === scope && g.revoked_at === null);
}

function OutgoingToggleRow({
  scope,
  granted,
  workspaceId,
  onChanged,
}: {
  scope: ConsentScope;
  granted: boolean;
  workspaceId: string;
  onChanged: (scope: ConsentScope, granted: boolean) => void;
}) {
  const { t } = useLocale();
  const [pending, setPending] = useState(false);
  const [error, setError] = useState(false);

  async function handleToggle() {
    // Kein Optimistic-Update: Zustand aendert sich erst nach der Response.
    setPending(true);
    setError(false);
    try {
      if (granted) {
        await api.workspaces.consent.revoke(workspaceId, { scope });
      } else {
        await api.workspaces.consent.grant(workspaceId, { scope });
      }
      onChanged(scope, !granted);
    } catch {
      setError(true);
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="flex flex-col gap-1 border-b border-white/5 py-3 last:border-0">
      <div className="flex items-center justify-between gap-3">
        <span className="text-sm text-ivory">{t(SCOPE_LABEL_KEYS[scope])}</span>
        <button
          type="button"
          role="switch"
          aria-checked={granted}
          aria-label={t(SCOPE_LABEL_KEYS[scope])}
          disabled={pending}
          onClick={handleToggle}
          className={cn(
            "relative h-6 w-11 shrink-0 rounded-full transition-colors disabled:opacity-50",
            granted ? "bg-gold" : "bg-white/15",
          )}
        >
          <span
            className={cn(
              "absolute top-0.5 h-5 w-5 rounded-full bg-background transition-transform",
              granted ? "translate-x-5" : "translate-x-0.5",
            )}
          />
        </button>
      </div>
      {error && <p className="text-xs text-danger">{t("app.consent.toggleError")}</p>}
    </div>
  );
}

function IncomingReadRow({ scope, granted }: { scope: ConsentScope; granted: boolean }) {
  const { t } = useLocale();
  return (
    <div className="flex items-center justify-between gap-3 border-b border-white/5 py-3 last:border-0">
      <span className="text-sm text-ivory">{t(SCOPE_LABEL_KEYS[scope])}</span>
      <Badge variant={granted ? "success" : "neutral"}>
        {t(granted ? "app.consent.grantedBadge" : "app.consent.notGrantedBadge")}
      </Badge>
    </div>
  );
}

function ConsentContent({ workspaceId }: { workspaceId: string }) {
  const { t } = useLocale();
  const { user } = useAuth();
  const consentState = useAsync(() => api.workspaces.consent.list(workspaceId), [workspaceId]);
  const overviewState = useAsync(() => api.workspaces.get(workspaceId), [workspaceId]);
  const [grants, setGrants] = useState<WorkspaceConsentOut | null>(null);

  if (consentState.status === "loading" || overviewState.status === "loading") {
    return <LoadingState label={t("common.loading")} />;
  }
  if (consentState.status === "error") {
    return <ErrorState error={consentState.error} onRetry={consentState.reload} />;
  }
  if (overviewState.status === "error") {
    return <ErrorState error={overviewState.error} onRetry={overviewState.reload} />;
  }

  const serverData = consentState.data;
  const data = grants ?? serverData;
  const counterpart = overviewState.data.dual_profile.find((m) => m.user_id !== user?.id);
  const counterpartName = counterpart?.display_name ?? "";

  function handleChanged(scope: ConsentScope, nowGranted: boolean) {
    setGrants((prev) => {
      const base = prev ?? serverData;
      const withoutScope = base.granted_by_me.filter((g: ConsentGrantOut) => g.scope !== scope);
      if (!nowGranted) {
        return { ...base, granted_by_me: withoutScope };
      }
      return {
        ...base,
        granted_by_me: [
          ...withoutScope,
          {
            id: `${scope}-local`,
            workspace_id: workspaceId,
            grantor_user_id: user?.id ?? "",
            grantee_user_id: "",
            scope,
            granted_at: new Date().toISOString(),
            revoked_at: null,
            version: 1,
          },
        ],
      };
    });
  }

  return (
    <div className="animate-rise-in flex flex-col gap-6">
      <Card>
        <CardHeader>
          <CardTitle className="text-base">{t("app.consent.sharedByMeTitle")}</CardTitle>
          <p className="text-sm text-muted">
            {t("app.consent.sharedByMeHintPrefix")} <strong className="text-ivory">{counterpartName}</strong>{" "}
            {t("app.consent.sharedByMeHintSuffix")}
          </p>
        </CardHeader>
        <CardContent>
          <p className="mb-2 text-xs uppercase tracking-wider text-bronze">{t("app.consent.defaultGroupTitle")}</p>
          {DEFAULT_SCOPES.map((scope) => (
            <OutgoingToggleRow
              key={scope}
              scope={scope}
              granted={isGranted(data.granted_by_me, scope)}
              workspaceId={workspaceId}
              onChanged={handleChanged}
            />
          ))}
          <p className="mb-2 mt-4 text-xs uppercase tracking-wider text-bronze">{t("app.consent.extendedGroupTitle")}</p>
          {EXTENDED_SCOPES.map((scope) => (
            <OutgoingToggleRow
              key={scope}
              scope={scope}
              granted={isGranted(data.granted_by_me, scope)}
              workspaceId={workspaceId}
              onChanged={handleChanged}
            />
          ))}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">{t("app.consent.sharedWithMeTitle")}</CardTitle>
          <p className="text-sm text-muted">
            {t("app.consent.sharedWithMeHintPrefix")} <strong className="text-ivory">{counterpartName}</strong>{" "}
            {t("app.consent.sharedWithMeHintSuffix")}
          </p>
        </CardHeader>
        <CardContent>
          <p className="mb-2 text-xs uppercase tracking-wider text-bronze">{t("app.consent.defaultGroupTitle")}</p>
          {DEFAULT_SCOPES.map((scope) => (
            <IncomingReadRow key={scope} scope={scope} granted={isGranted(data.granted_to_me, scope)} />
          ))}
          <p className="mb-2 mt-4 text-xs uppercase tracking-wider text-bronze">{t("app.consent.extendedGroupTitle")}</p>
          {EXTENDED_SCOPES.map((scope) => (
            <IncomingReadRow key={scope} scope={scope} granted={isGranted(data.granted_to_me, scope)} />
          ))}
        </CardContent>
      </Card>
    </div>
  );
}

export default function WorkspaceConsentPage() {
  const params = useParams<{ id: string }>();
  return (
    <AppShell>
      <ConsentContent workspaceId={params.id} />
    </AppShell>
  );
}
