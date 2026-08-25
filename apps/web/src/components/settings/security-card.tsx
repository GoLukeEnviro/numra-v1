"use client";

import { useState, type FormEvent } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { LoadingState, ErrorState } from "@/components/ui/states";
import { api, ApiError } from "@/api/client";
import { useAsync } from "@/lib/use-async";
import { formatDateTime } from "@/lib/utils";
import { useLocale } from "@/i18n/context";
import { ShieldCheck, KeyRound, Laptop } from "lucide-react";

/**
 * V1.5 Epic N: change password (requires the current password even though the
 * caller already has a valid session) and manage active sessions ("log out other
 * devices"). Both actions hit the real backend -- there is no local-only state here.
 */
function ChangePasswordForm() {
  const { t } = useLocale();
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<{ code: string; message: string } | null>(null);
  const [success, setSuccess] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setSuccess(false);

    if (newPassword !== confirmPassword) {
      setError({ code: "PASSWORD_MISMATCH", message: t("app.security.mismatch") });
      return;
    }

    setSubmitting(true);
    try {
      await api.auth.changePassword({
        current_password: currentPassword,
        new_password: newPassword,
      });
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
      setSuccess(true);
    } catch (err) {
      setError(
        err instanceof ApiError
          ? { code: err.code, message: err.message }
          : { code: "NETWORK_ERROR", message: t("common.networkError") },
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-4">
      <div>
        <Label htmlFor="current-password">{t("app.security.currentPassword")}</Label>
        <Input
          id="current-password"
          type="password"
          autoComplete="current-password"
          value={currentPassword}
          onChange={(e) => setCurrentPassword(e.target.value)}
          required
        />
      </div>
      <div>
        <Label htmlFor="new-password">{t("app.security.newPassword")}</Label>
        <Input
          id="new-password"
          type="password"
          autoComplete="new-password"
          minLength={12}
          value={newPassword}
          onChange={(e) => setNewPassword(e.target.value)}
          required
        />
      </div>
      <div>
        <Label htmlFor="confirm-password">{t("app.security.confirmPassword")}</Label>
        <Input
          id="confirm-password"
          type="password"
          autoComplete="new-password"
          minLength={12}
          value={confirmPassword}
          onChange={(e) => setConfirmPassword(e.target.value)}
          required
        />
      </div>

      {error && (
        <div role="alert" className="rounded-lg border border-danger/30 bg-danger-surface p-3 text-sm text-text">
          <span className="mr-1.5 rounded bg-black/20 px-1.5 py-0.5 font-mono text-xs">
            {error.code}
          </span>
          {error.message}
        </div>
      )}
      {success && (
        <p role="status" className="text-sm text-gold">
          {t("app.security.changed")}
        </p>
      )}

      <Button type="submit" size="sm" loading={submitting} className="self-start">
        <KeyRound className="h-3.5 w-3.5" aria-hidden="true" />
        {t("app.security.changeButton")}
      </Button>
    </form>
  );
}

function ActiveSessions() {
  const { t } = useLocale();
  const state = useAsync(() => api.auth.sessions(), []);
  const [revoking, setRevoking] = useState(false);
  const [revoked, setRevoked] = useState(false);

  async function handleRevokeOthers() {
    setRevoking(true);
    try {
      await api.auth.revokeOtherSessions();
      setRevoked(true);
      state.reload();
    } finally {
      setRevoking(false);
    }
  }

  if (state.status === "loading") return <LoadingState label={t("app.security.loadingSessions")} />;
  if (state.status === "error") {
    return (
      <ErrorState error={state.error} onRetry={state.reload} title={t("app.security.sessionsErrorTitle")} />
    );
  }

  const otherCount = state.data.filter((s) => !s.is_current).length;

  return (
    <div>
      <ul className="flex flex-col gap-2">
        {state.data.map((session) => (
          <li
            key={session.id}
            className="flex items-center justify-between gap-3 rounded-lg border border-white/10 bg-surface-2 px-4 py-2.5 text-sm"
          >
            <div className="flex items-center gap-2.5">
              <Laptop className="h-4 w-4 text-muted" aria-hidden="true" />
              <div>
                <p className="text-text">
                  {session.is_current ? t("app.security.thisDevice") : t("app.security.otherDevice")}
                </p>
                <p className="text-xs text-muted">
                  {t("app.security.signedIn")} {formatDateTime(session.created_at)}
                </p>
              </div>
            </div>
            {session.is_current && (
              <span className="rounded-full bg-gold/10 px-2 py-0.5 text-[11px] text-gold">
                {t("app.security.current")}
              </span>
            )}
          </li>
        ))}
      </ul>

      {otherCount > 0 && (
        <Button
          type="button"
          variant="secondary"
          size="sm"
          className="mt-4"
          loading={revoking}
          onClick={handleRevokeOthers}
        >
          {t("app.security.logoutOthers")} ({otherCount})
        </Button>
      )}
      {revoked && (
        <p role="status" className="mt-2 text-xs text-muted">
          {t("app.security.othersLoggedOut")}
        </p>
      )}
    </div>
  );
}

export function SecurityCard() {
  const { t } = useLocale();
  return (
    <Card>
      <CardHeader>
        <div className="mb-1 flex items-center gap-2">
          <ShieldCheck className="h-5 w-5 text-gold" aria-hidden="true" />
          <CardTitle className="text-base">{t("app.security.title")}</CardTitle>
        </div>
        <CardDescription>{t("app.security.body")}</CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-6">
        <ChangePasswordForm />
        <div className="border-t border-white/10 pt-6">
          <p className="mb-3 text-sm text-ivory">{t("app.security.activeSessions")}</p>
          <ActiveSessions />
        </div>
      </CardContent>
    </Card>
  );
}
