"use client";

import { useState } from "react";
import { api } from "@/api/client";
import { Button } from "@/components/ui/button";
import { useLocale } from "@/i18n/context";
import { useAuth } from "@/lib/auth-context";
import { ShieldCheck } from "lucide-react";

/**
 * D2: Hinweis fuer Bestandskonten ohne 18+-Erklaerung (`user.age_confirmed_at == null`).
 * Bewusst kein harter Gate und nicht ausblendbar: die App bleibt voll nutzbar, der Weg zur
 * Bestaetigung ist aber immer sichtbar. Kostenintensive Aktionen fuer unbestaetigte Konten
 * zu sperren ist Sache von D4 (Schnittstelle: `age_confirmed_at` aus `/v1/auth/me`).
 */
export function AgeConfirmationBanner() {
  const { t } = useLocale();
  const { status, user, refresh } = useAuth();
  const [checked, setChecked] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<"unchecked" | "failed" | null>(null);

  if (status !== "authenticated") return null;
  if (user == null || user.age_confirmed_at != null) return null;

  async function handleConfirm() {
    if (!checked) {
      setError("unchecked");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await api.auth.confirmAge();
      await refresh();
    } catch {
      setError("failed");
    } finally {
      setSaving(false);
    }
  }

  return (
    <section
      role="region"
      aria-label={t("app.ageBanner.title")}
      className="mb-4 rounded-lg border border-gold/30 bg-gold/10 px-4 py-3 text-sm text-text"
    >
      <div className="flex items-start gap-3">
        <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-gold" aria-hidden="true" />
        <div className="flex-1">
          <p className="font-medium text-ivory">{t("app.ageBanner.title")}</p>
          <p className="mt-1 text-muted">{t("app.ageBanner.body")}</p>
          <label className="mt-3 flex items-center gap-2">
            <input
              type="checkbox"
              checked={checked}
              onChange={(e) => setChecked(e.target.checked)}
            />
            {t("app.ageBanner.checkbox")}
          </label>
          {error && (
            <p role="alert" className="mt-2 text-xs text-danger">
              {t(error === "unchecked" ? "app.ageBanner.errorUnchecked" : "app.ageBanner.errorFailed")}
            </p>
          )}
        </div>
        <Button type="button" size="sm" variant="secondary" loading={saving} onClick={handleConfirm}>
          {t("app.ageBanner.confirm")}
        </Button>
      </div>
    </section>
  );
}
