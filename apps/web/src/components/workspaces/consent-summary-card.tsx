"use client";

import Link from "next/link";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ErrorState, LoadingState } from "@/components/ui/states";
import { useLocale } from "@/i18n/context";
import { useAsync } from "@/lib/use-async";
import { summarizeConsent } from "@/lib/workspace-consent";
import { api } from "@/api/client";

export interface ConsentSummaryCardProps {
  workspaceId: string;
  counterpartName: string;
}

/** Aggregated consent overview for the hub -- stays visible even on a DISSOLVED
 *  workspace, since `GET /v1/workspaces/{id}/consent` keeps working after
 *  dissolution (verified IST-Stand). */
export function ConsentSummaryCard({ workspaceId, counterpartName }: ConsentSummaryCardProps) {
  const { t } = useLocale();
  const consentState = useAsync(() => api.workspaces.consent.list(workspaceId), [workspaceId]);

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">{t("app.relationshipWorkspace.consentSummaryTitle")}</CardTitle>
      </CardHeader>
      <CardContent>
        {consentState.status === "loading" && <LoadingState label={t("common.loading")} />}
        {consentState.status === "error" && (
          <ErrorState error={consentState.error} onRetry={consentState.reload} />
        )}
        {consentState.status === "success" && (
          <div className="flex flex-col gap-2">
            {(() => {
              const summary = summarizeConsent(consentState.data);
              return (
                <>
                  <p className="text-sm text-text">
                    {t("app.relationshipWorkspace.consentSummaryByMePrefix")} {summary.grantedByMeCount}{" "}
                    {t("app.relationshipWorkspace.consentSummaryByMeSuffix")}
                  </p>
                  <p className="text-sm text-text">
                    <strong className="text-ivory">{counterpartName}</strong>{" "}
                    {t("app.relationshipWorkspace.consentSummaryToMeMiddle")} {summary.grantedToMeCount}{" "}
                    {t("app.relationshipWorkspace.consentSummaryToMeSuffix")}
                  </p>
                </>
              );
            })()}
            <Link href={`/workspaces/${workspaceId}/consent`} className="mt-1 text-sm text-bronze hover:underline">
              {t("app.relationshipWorkspace.consentSummaryCta")}
            </Link>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
