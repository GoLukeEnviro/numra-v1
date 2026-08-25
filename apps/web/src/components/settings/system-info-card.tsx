"use client";

import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { LoadingState, ErrorState } from "@/components/ui/states";
import { api } from "@/api/client";
import { useAsync } from "@/lib/use-async";
import { useLocale } from "@/i18n/context";
import { Info } from "lucide-react";

/**
 * V1.5 Epic N: GET /v1/system-info is already sanitized server-side (see
 * numra_api.schemas.auth.SystemInfoOut) -- this component renders exactly what it
 * returns, no secret ever passes through here.
 */
export function SystemInfoCard() {
  const { t } = useLocale();
  const state = useAsync(() => api.systemInfo.get(), []);

  return (
    <Card>
      <CardHeader>
        <div className="mb-1 flex items-center gap-2">
          <Info className="h-5 w-5 text-gold" aria-hidden="true" />
          <CardTitle className="text-base">{t("app.systemInfo.title")}</CardTitle>
        </div>
        <CardDescription>{t("app.systemInfo.body")}</CardDescription>
      </CardHeader>
      <CardContent>
        {state.status === "loading" && <LoadingState label={t("common.loading")} />}
        {state.status === "error" && (
          <ErrorState error={state.error} onRetry={state.reload} title={t("app.systemInfo.errorTitle")} />
        )}
        {state.status === "success" && (
          <dl className="grid gap-x-6 gap-y-3 text-xs sm:grid-cols-2">
            <div>
              <dt className="text-muted">{t("app.systemInfo.environment")}</dt>
              <dd className="mt-0.5 font-mono text-text">{state.data.environment}</dd>
            </div>
            <div>
              <dt className="text-muted">{t("app.systemInfo.timezone")}</dt>
              <dd className="mt-0.5 font-mono text-text">{state.data.app_timezone}</dd>
            </div>
            <div>
              <dt className="text-muted">{t("app.systemInfo.sessionLifetime")}</dt>
              <dd className="mt-0.5 font-mono text-text">{state.data.session_ttl_hours}h</dd>
            </div>
            <div>
              <dt className="text-muted">{t("app.systemInfo.selfSignup")}</dt>
              <dd className="mt-0.5 font-mono text-text">
                {state.data.self_signup_enabled ? t("app.systemInfo.enabled") : t("app.systemInfo.disabled")}
              </dd>
            </div>
            <div>
              <dt className="text-muted">{t("app.systemInfo.llmProvider")}</dt>
              <dd className="mt-0.5 font-mono text-text">{state.data.llm_provider}</dd>
            </div>
            <div>
              <dt className="text-muted">{t("app.systemInfo.pdfExport")}</dt>
              <dd className="mt-0.5 font-mono text-text">
                {state.data.pdf_export_enabled ? t("app.systemInfo.enabled") : t("app.systemInfo.disabled")}
              </dd>
            </div>
          </dl>
        )}
      </CardContent>
    </Card>
  );
}
