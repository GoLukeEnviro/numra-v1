"use client";

import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { LoadingState, ErrorState } from "@/components/ui/states";
import { api, type EntitlementSetOut } from "@/api/client";
import { useAsync } from "@/lib/use-async";
import { useLocale } from "@/i18n/context";
import type { MessageKey } from "@/i18n/catalog";
import { Check, Minus, Sparkles, X } from "lucide-react";

const FEATURE_FLAGS: { key: keyof EntitlementSetOut; labelKey: MessageKey }[] = [
  { key: "personal_workspace", labelKey: "app.entitlements.personalWorkspace" },
  { key: "connections", labelKey: "app.entitlements.connections" },
  { key: "relationship_workspaces", labelKey: "app.entitlements.relationshipWorkspaces" },
  { key: "relationship_checkins", labelKey: "app.entitlements.relationshipCheckins" },
  { key: "relationship_copilot", labelKey: "app.entitlements.relationshipCopilot" },
  {
    key: "advanced_relationship_analysis",
    labelKey: "app.entitlements.advancedRelationshipAnalysis",
  },
  { key: "life_tracking", labelKey: "app.entitlements.lifeTracking" },
  { key: "premium_reports", labelKey: "app.entitlements.premiumReports" },
];

const LIMIT_FIELDS: { key: keyof EntitlementSetOut; labelKey: MessageKey }[] = [
  { key: "max_connections", labelKey: "app.entitlements.maxConnections" },
  { key: "max_workspaces", labelKey: "app.entitlements.maxWorkspaces" },
];

function FeatureRow({ label, enabled }: { label: string; enabled: boolean }) {
  return (
    <li className="flex items-center justify-between gap-3 border-b border-white/5 py-2 text-sm last:border-0">
      <span className="text-text">{label}</span>
      {enabled ? (
        <Check className="h-4 w-4 shrink-0 text-success" aria-hidden="true" />
      ) : (
        <X className="h-4 w-4 shrink-0 text-muted" aria-hidden="true" />
      )}
    </li>
  );
}

function LimitRow({ label, value, unlimitedLabel }: { label: string; value: number | null; unlimitedLabel: string }) {
  return (
    <li className="flex items-center justify-between gap-3 border-b border-white/5 py-2 text-sm last:border-0">
      <span className="text-text">{label}</span>
      {value === null ? (
        <span className="flex items-center gap-1 text-muted">
          <Minus className="h-3.5 w-3.5" aria-hidden="true" />
          {unlimitedLabel}
        </span>
      ) : (
        <span className="text-text">{value}</span>
      )}
    </li>
  );
}

/**
 * Read-only overview of the signed-in user's effective entitlement bundle
 * (GET /v1/me/entitlements). Deliberately no feature-gating anywhere in this
 * component -- it only informs, it never disables anything based on these
 * values.
 */
export function EntitlementsCard() {
  const { t } = useLocale();
  const state = useAsync(() => api.entitlements.get(), []);

  return (
    <Card>
      <CardHeader>
        <div className="mb-1 flex items-center gap-2">
          <Sparkles className="h-5 w-5 text-gold" aria-hidden="true" />
          <CardTitle className="text-base">{t("app.entitlements.title")}</CardTitle>
        </div>
        <CardDescription>{t("app.entitlements.body")}</CardDescription>
      </CardHeader>
      <CardContent>
        {state.status === "loading" && <LoadingState label={t("app.entitlements.loading")} />}
        {state.status === "error" && (
          <ErrorState
            error={state.error}
            onRetry={state.reload}
            title={t("app.entitlements.errorTitle")}
          />
        )}
        {state.status === "success" && (
          <ul>
            {FEATURE_FLAGS.map(({ key, labelKey }) => (
              <FeatureRow
                key={key}
                label={t(labelKey)}
                enabled={Boolean(state.data[key])}
              />
            ))}
            {LIMIT_FIELDS.map(({ key, labelKey }) => (
              <LimitRow
                key={key}
                label={t(labelKey)}
                value={state.data[key] as number | null}
                unlimitedLabel={t("app.entitlements.unlimited")}
              />
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
