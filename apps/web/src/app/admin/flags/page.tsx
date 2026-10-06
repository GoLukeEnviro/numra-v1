"use client";

import { useState } from "react";
import { ErrorState, LoadingState } from "@/components/ui/states";
import { useLocale } from "@/i18n/context";
import { useAsync } from "@/lib/use-async";
import { cn } from "@/lib/utils";
import { api, type FeatureFlagOut } from "@/api/client";
import type { MessageKey } from "@/i18n/catalog";

/** Reihenfolge entspricht der Master->Phase-Abhaengigkeit aus services/feature_flags.py. */
const FLAG_ORDER = [
  "v2_master",
  "connections",
  "relationship_workspaces",
  "checkins",
  "tasks",
  "copilot",
  "evidence_layer",
] as const;

function sortFlags(flags: FeatureFlagOut[]): FeatureFlagOut[] {
  return [...flags].sort((a, b) => FLAG_ORDER.indexOf(a.name as (typeof FLAG_ORDER)[number]) - FLAG_ORDER.indexOf(b.name as (typeof FLAG_ORDER)[number]));
}

function FlagRow({ flag, onChanged }: { flag: FeatureFlagOut; onChanged: () => Promise<void> }) {
  const { t, locale } = useLocale();
  const [pending, setPending] = useState(false);
  const [error, setError] = useState(false);
  const nameKey = `admin.flags.name.${flag.name}` as MessageKey;
  const descKey = `admin.flags.desc.${flag.name}` as MessageKey;

  async function handleToggle() {
    // Kein Optimistic-Update: Zustand aendert sich erst nach der Response
    // (gleiches Muster wie app/workspaces/[id]/consent/page.tsx).
    setPending(true);
    setError(false);
    try {
      await api.admin.flags.update(flag.name, { enabled: !flag.enabled });
      // PATCH liefert 204 ohne Body: Serverzustand (inkl. updated_by_user_id) neu laden.
      await onChanged();
    } catch {
      setError(true);
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="flex flex-col gap-1 border-b border-white/5 py-4 last:border-0">
      <div className="flex items-center justify-between gap-3">
        <div className="min-w-0">
          <p className="text-sm font-medium text-ivory">{t(nameKey)}</p>
          <p className="mt-0.5 text-xs text-muted">{t(descKey)}</p>
          <p className="mt-1 text-[11px] text-muted">
            {t("admin.flags.lastChanged")}:{" "}
            {flag.updated_by_user_id
              ? new Date(flag.updated_at).toLocaleString(locale)
              : t("admin.flags.never")}
          </p>
        </div>
        <button
          type="button"
          role="switch"
          aria-checked={flag.enabled}
          aria-label={t(nameKey)}
          disabled={pending}
          onClick={handleToggle}
          className={cn(
            "relative h-6 w-11 shrink-0 rounded-full transition-colors disabled:opacity-50",
            flag.enabled ? "bg-gold" : "bg-white/15",
          )}
        >
          <span
            className={cn(
              "absolute top-0.5 h-5 w-5 rounded-full bg-background transition-transform",
              flag.enabled ? "translate-x-5" : "translate-x-0.5",
            )}
          />
        </button>
      </div>
      {error && <p className="text-xs text-danger">{t("admin.flags.toggleError")}</p>}
    </div>
  );
}

export default function AdminFlagsPage() {
  const { t } = useLocale();
  const flagsState = useAsync(() => api.admin.flags.list(), []);
  const [flags, setFlags] = useState<FeatureFlagOut[] | null>(null);

  const current = flags ?? (flagsState.status === "success" ? sortFlags(flagsState.data.flags) : null);

  async function handleChanged() {
    const { flags: fresh } = await api.admin.flags.list();
    setFlags(sortFlags(fresh));
  }

  return (
    <div className="animate-rise-in">
      <header className="mb-8">
        <h1 className="font-serif text-3xl text-ivory">{t("admin.flags.title")}</h1>
        <p className="mt-1 text-sm text-muted">{t("admin.flags.subtitle")}</p>
      </header>

      {flagsState.status === "loading" && <LoadingState label={t("admin.flags.loading")} />}
      {flagsState.status === "error" && (
        <ErrorState error={flagsState.error} onRetry={flagsState.reload} title={t("admin.common.errorTitle")} />
      )}
      {current && (
        <div className="rounded-xl border border-white/10 bg-surface px-5">
          {current.map((flag) => (
            <FlagRow key={flag.name} flag={flag} onChanged={handleChanged} />
          ))}
        </div>
      )}
    </div>
  );
}
