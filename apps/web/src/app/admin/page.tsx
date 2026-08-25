"use client";

import { api, type AdminStatsOut } from "@/api/client";
import { ErrorState, LoadingState } from "@/components/ui/states";
import type { MessageKey } from "@/i18n/catalog";
import { useLocale } from "@/i18n/context";
import { useAsync } from "@/lib/use-async";

/**
 * Exactly the nine counters `GET /v1/admin/stats` returns — no derived rates, no
 * trends, no invented indicators. If a number is not in the payload it is not shown.
 */
const TILES = [
  { key: "total_users", labelKey: "admin.stats.totalUsers" },
  { key: "active_users", labelKey: "admin.stats.activeUsers" },
  { key: "disabled_users", labelKey: "admin.stats.disabledUsers" },
  { key: "registrations_last_7_days", labelKey: "admin.stats.registrations7" },
  { key: "registrations_last_30_days", labelKey: "admin.stats.registrations30" },
  { key: "active_sessions", labelKey: "admin.stats.activeSessions" },
  { key: "total_people", labelKey: "admin.stats.totalPeople" },
  { key: "total_calculations", labelKey: "admin.stats.totalCalculations" },
  { key: "total_reports", labelKey: "admin.stats.totalReports" },
] as const satisfies readonly { key: keyof AdminStatsOut; labelKey: MessageKey }[];

export default function AdminDashboardPage() {
  const { t } = useLocale();
  const statsState = useAsync(() => api.admin.stats(), []);

  return (
    <div className="animate-rise-in">
      <header className="mb-8">
        <h1 className="font-serif text-3xl text-ivory">{t("admin.dashboard.title")}</h1>
        <p className="mt-1 text-sm text-muted">{t("admin.dashboard.subtitle")}</p>
      </header>

      {statsState.status === "loading" && <LoadingState label={t("admin.dashboard.loading")} />}
      {statsState.status === "error" && (
        <ErrorState
          error={statsState.error}
          onRetry={statsState.reload}
          title={t("admin.common.errorTitle")}
        />
      )}
      {statsState.status === "success" && (
        <dl className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {TILES.map(({ key, labelKey }) => (
            <div
              key={key}
              className="rounded-xl border border-white/10 bg-surface p-5 shadow-[0_1px_0_0_rgba(255,255,255,0.03)_inset]"
            >
              <dt className="text-sm text-muted">{t(labelKey)}</dt>
              <dd className="mt-2 font-serif text-3xl text-ivory">{statsState.data[key]}</dd>
            </div>
          ))}
        </dl>
      )}
    </div>
  );
}
