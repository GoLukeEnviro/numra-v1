"use client";

import { Suspense, useState, type FormEvent } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { api, ApiError } from "@/api/client";
import { Logo } from "@/components/brand/logo";
import { NumericWheel } from "@/components/layout/numeric-wheel";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { LoadingState } from "@/components/ui/states";
import { useLocale } from "@/i18n/context";
import { AlertTriangle, CheckCircle2, KeyRound } from "lucide-react";

const MIN_PASSWORD_LENGTH = 12;

type Phase = "form" | "submitting" | "success" | "token-invalid" | "rate-limited" | "network-error";

/** Visually calm, ruhiges Muster fuer erwartete End-States (kein Rot, kein
 *  AlertTriangle, role="status") -- wie PhaseDisabledState, aber seitenlokal, da
 *  states.tsx's PhaseErrorCode-Union fuer andere Zwecke fest typisiert ist. */
function QuietState({
  icon: Icon,
  title,
  body,
  action,
}: {
  icon: typeof CheckCircle2;
  title: string;
  body: string;
  action?: React.ReactNode;
}) {
  return (
    <div role="status" className="flex flex-col items-center gap-3 py-4 text-center">
      <Icon className="h-6 w-6 text-gold" aria-hidden="true" />
      <p className="text-sm font-medium text-ivory">{title}</p>
      <p className="text-sm text-muted">{body}</p>
      {action}
    </div>
  );
}

function ResetPasswordForm({ token }: { token: string }) {
  const { t } = useLocale();
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [phase, setPhase] = useState<Phase>("form");
  const [validationError, setValidationError] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setValidationError(null);

    if (newPassword.length < MIN_PASSWORD_LENGTH) {
      setValidationError(t("public.resetPassword.errorTooShort"));
      return;
    }
    if (newPassword !== confirmPassword) {
      setValidationError(t("public.resetPassword.errorMismatch"));
      return;
    }

    setPhase("submitting");
    try {
      await api.auth.resetPassword({ token, new_password: newPassword });
      setPhase("success");
    } catch (err) {
      if (err instanceof ApiError && err.code === "INVALID_OR_EXPIRED_TOKEN") {
        setPhase("token-invalid");
      } else if (err instanceof ApiError && err.status === 429) {
        setPhase("rate-limited");
      } else {
        setPhase("network-error");
      }
    }
  }

  if (phase === "success") {
    return (
      <QuietState
        icon={CheckCircle2}
        title={t("public.resetPassword.successTitle")}
        body={t("public.resetPassword.successBody")}
        action={
          <Link
            href="/login"
            className="mt-2 text-sm text-gold underline-offset-4 hover:underline"
          >
            {t("public.resetPassword.successCta")}
          </Link>
        }
      />
    );
  }

  if (phase === "token-invalid") {
    return (
      <QuietState
        icon={KeyRound}
        title={t("public.resetPassword.invalidTitle")}
        body={t("public.resetPassword.invalidBody")}
        action={
          <Link
            href="/forgot-password"
            className="mt-2 text-sm text-gold underline-offset-4 hover:underline"
          >
            {t("public.resetPassword.invalidCta")}
          </Link>
        }
      />
    );
  }

  const bannerError =
    phase === "rate-limited"
      ? t("public.resetPassword.errorRateLimited")
      : phase === "network-error"
        ? t("common.networkError")
        : validationError;

  return (
    <form onSubmit={handleSubmit} noValidate>
      <div className="mb-4">
        <Label htmlFor="newPassword">{t("public.resetPassword.newPassword")}</Label>
        <Input
          id="newPassword"
          name="newPassword"
          type="password"
          autoComplete="new-password"
          minLength={MIN_PASSWORD_LENGTH}
          required
          aria-describedby="new-password-hint"
          value={newPassword}
          onChange={(e) => setNewPassword(e.target.value)}
        />
        <p id="new-password-hint" className="mt-1.5 text-xs text-muted">
          {t("public.resetPassword.passwordHint")}
        </p>
      </div>
      <div className="mb-5">
        <Label htmlFor="confirmPassword">{t("public.resetPassword.confirmPassword")}</Label>
        <Input
          id="confirmPassword"
          name="confirmPassword"
          type="password"
          autoComplete="new-password"
          minLength={MIN_PASSWORD_LENGTH}
          required
          value={confirmPassword}
          onChange={(e) => setConfirmPassword(e.target.value)}
        />
      </div>

      {bannerError && (
        <div
          role="alert"
          className="mb-4 flex items-start gap-2 rounded-lg border border-danger/30 bg-danger-surface p-3 text-sm text-text"
        >
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-danger" aria-hidden="true" />
          <span>{bannerError}</span>
        </div>
      )}

      <Button type="submit" className="w-full" loading={phase === "submitting"}>
        {t("public.resetPassword.submit")}
      </Button>
    </form>
  );
}

function MissingToken() {
  const { t } = useLocale();
  return (
    <QuietState
      icon={KeyRound}
      title={t("public.resetPassword.missingTokenTitle")}
      body={t("public.resetPassword.missingTokenBody")}
      action={
        <Link
          href="/forgot-password"
          className="mt-2 text-sm text-gold underline-offset-4 hover:underline"
        >
          {t("public.resetPassword.invalidCta")}
        </Link>
      }
    />
  );
}

function ResetPasswordGate() {
  const searchParams = useSearchParams();
  const token = searchParams.get("token");
  if (!token) return <MissingToken />;
  return <ResetPasswordForm token={token} />;
}

export default function ResetPasswordPage() {
  const { t } = useLocale();
  return (
    <div className="sacred-wheel-bg relative flex min-h-screen items-center justify-center overflow-hidden bg-background p-6">
      <NumericWheel className="pointer-events-none absolute -right-24 -top-24 h-96 w-96 opacity-40" />
      <NumericWheel className="pointer-events-none absolute -bottom-32 -left-32 h-96 w-96 opacity-20" />

      <Card className="relative w-full max-w-sm animate-rise-in shadow-elevated">
        <CardHeader className="text-center">
          <CardTitle className="text-2xl">
            <Logo className="justify-center" markClassName="h-10 w-10" textClassName="text-2xl" />
            <span className="sr-only">{t("public.resetPassword.title")}</span>
          </CardTitle>
          <CardDescription>{t("public.resetPassword.subtitle")}</CardDescription>
        </CardHeader>
        <CardContent>
          <Suspense fallback={<LoadingState label={t("common.loading")} />}>
            <ResetPasswordGate />
          </Suspense>
        </CardContent>
      </Card>
    </div>
  );
}
