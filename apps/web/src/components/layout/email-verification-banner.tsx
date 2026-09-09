"use client";

import { useState } from "react";
import { api } from "@/api/client";
import { Button } from "@/components/ui/button";
import { useLocale } from "@/i18n/context";
import { useAuth } from "@/lib/auth-context";
import { MailWarning, X } from "lucide-react";

/**
 * V2: shown only for a signed-in user whose email is not yet verified
 * (`user.email_verified_at == null`). Dismissable per session only -- no
 * localStorage, so it reappears on the next visit until the address is
 * actually verified (the backend already rate-limits repeated resend
 * requests, so this component adds no cooldown of its own).
 */
export function EmailVerificationBanner() {
  const { t } = useLocale();
  const { status, user } = useAuth();
  const [dismissed, setDismissed] = useState(false);
  const [resending, setResending] = useState(false);
  const [resent, setResent] = useState(false);

  if (dismissed) return null;
  if (status !== "authenticated") return null;
  if (user?.email_verified_at != null) return null;

  async function handleResend() {
    setResending(true);
    try {
      await api.auth.requestEmailVerification();
      setResent(true);
    } finally {
      setResending(false);
    }
  }

  return (
    <div
      role="status"
      className="mb-4 flex items-center gap-3 rounded-lg border border-gold/30 bg-gold/10 px-4 py-3 text-sm text-text"
    >
      <MailWarning className="h-4 w-4 shrink-0 text-gold" aria-hidden="true" />
      <div className="flex-1">
        <p>{t("app.emailVerificationBanner.body")}</p>
        {resent && (
          <p className="mt-1 text-xs text-muted">{t("app.emailVerificationBanner.resendSent")}</p>
        )}
      </div>
      {!resent && (
        <Button type="button" size="sm" variant="secondary" loading={resending} onClick={handleResend}>
          {t("app.emailVerificationBanner.resend")}
        </Button>
      )}
      <button
        type="button"
        aria-label={t("app.emailVerificationBanner.dismiss")}
        onClick={() => setDismissed(true)}
        className="rounded p-1 text-muted hover:bg-white/5 hover:text-ivory"
      >
        <X className="h-4 w-4" aria-hidden="true" />
      </button>
    </div>
  );
}
