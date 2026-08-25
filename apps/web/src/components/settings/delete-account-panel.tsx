"use client";

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { api, ApiError } from "@/api/client";
import { useAuth } from "@/lib/auth-context";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useLocale } from "@/i18n/context";
import type { MessageKey } from "@/i18n/catalog";
import { AlertTriangle, Trash2 } from "lucide-react";

const DELETED_ITEM_KEYS: MessageKey[] = [
  "app.deleteAccount.itemProfiles",
  "app.deleteAccount.itemCalculations",
  "app.deleteAccount.itemRelationships",
  "app.deleteAccount.itemReports",
  "app.deleteAccount.itemExports",
  "app.deleteAccount.itemAccount",
];

/**
 * Account deletion.
 *
 * `POST /v1/account/delete-all` verifies the password server-side, removes the
 * physical export files *before* touching any database row, and clears the session
 * cookies in its response. The client therefore treats its own auth state as stale
 * the moment the call succeeds: it refreshes from the server and leaves for /login
 * rather than continuing to render an authenticated shell around a deleted account.
 */
export function DeleteAccountPanel() {
  const router = useRouter();
  const { refresh } = useAuth();
  const { t } = useLocale();
  const [confirming, setConfirming] = useState(false);
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<{ code: string; message: string } | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (password.length === 0) return;
    setSubmitting(true);
    setError(null);
    try {
      await api.account.deleteAll({ password });
      setPassword("");
      // The server invalidated the session and cleared the cookies; the local auth
      // context is now wrong until it re-checks.
      await refresh();
      router.replace("/login");
    } catch (err) {
      setSubmitting(false);
      if (err instanceof ApiError && err.code === "INVALID_CREDENTIALS") {
        setError({
          code: err.code,
          message: t("app.deleteAccount.wrongPassword"),
        });
      } else if (err instanceof ApiError) {
        setError({ code: err.code, message: err.message });
      } else {
        setError({ code: "NETWORK_ERROR", message: t("common.networkError") });
      }
    }
  }

  return (
    <Card className="border-danger/30">
      <CardHeader>
        <div className="flex items-center gap-2">
          <AlertTriangle className="h-5 w-5 text-danger" aria-hidden="true" />
          <CardTitle className="text-base">{t("app.deleteAccount.title")}</CardTitle>
        </div>
        <CardDescription>{t("app.deleteAccount.body")}</CardDescription>
      </CardHeader>
      <CardContent>
        {!confirming ? (
          <Button variant="secondary" onClick={() => setConfirming(true)}>
            <Trash2 className="h-4 w-4" aria-hidden="true" />
            {t("app.deleteAccount.title")}
          </Button>
        ) : (
          <div className="rounded-lg border border-danger/30 bg-danger-surface p-5">
            <p className="text-sm font-medium text-ivory">{t("app.deleteAccount.listIntro")}</p>
            <ul className="mt-3 list-disc space-y-1 pl-5 text-sm text-text">
              {DELETED_ITEM_KEYS.map((key) => (
                <li key={key}>{t(key)}</li>
              ))}
            </ul>
            <p className="mt-4 text-sm text-text">{t("app.deleteAccount.exportHint")}</p>

            <form onSubmit={handleSubmit} className="mt-5" noValidate>
              <div className="max-w-sm">
                <Label htmlFor="delete-password">{t("app.deleteAccount.confirmLabel")}</Label>
                <Input
                  id="delete-password"
                  type="password"
                  autoComplete="current-password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  disabled={submitting}
                />
              </div>

              {error && (
                <div
                  role="alert"
                  className="mt-4 flex items-start gap-2 rounded-lg border border-danger/40 bg-black/20 p-3 text-sm text-text"
                >
                  <AlertTriangle
                    className="mt-0.5 h-4 w-4 shrink-0 text-danger"
                    aria-hidden="true"
                  />
                  <span>
                    <span className="mr-1.5 rounded bg-black/25 px-1.5 py-0.5 font-mono text-xs">
                      {error.code}
                    </span>
                    {error.message}
                  </span>
                </div>
              )}

              <div className="mt-5 flex flex-wrap items-center gap-3">
                <Button
                  type="submit"
                  variant="danger"
                  loading={submitting}
                  disabled={password.length === 0}
                >
                  <Trash2 className="h-4 w-4" aria-hidden="true" />
                  {submitting ? t("app.deleteAccount.submitting") : t("app.deleteAccount.submit")}
                </Button>
                <Button
                  type="button"
                  variant="ghost"
                  disabled={submitting}
                  onClick={() => {
                    setConfirming(false);
                    setPassword("");
                    setError(null);
                  }}
                >
                  {t("app.deleteAccount.cancel")}
                </Button>
              </div>
            </form>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
