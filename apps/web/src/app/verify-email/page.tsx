"use client";

import { Suspense, useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { api, ApiError } from "@/api/client";
import { Logo } from "@/components/brand/logo";
import { NumericWheel } from "@/components/layout/numeric-wheel";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { LoadingState } from "@/components/ui/states";
import { useLocale } from "@/i18n/context";
import { useAuth } from "@/lib/auth-context";
import { AlertTriangle, CheckCircle2, MailQuestion } from "lucide-react";

type Phase = "verifying" | "success" | "token-invalid" | "rate-limited" | "network-error";

/** Ruhiges, seitenlokales Muster fuer erwartete End-States (kein Rot, kein
 *  AlertTriangle, role="status") -- states.tsx's PhaseErrorCode-Union ist fuer
 *  andere Zwecke fest typisiert und bleibt unangetastet. */
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

function ResendVerification() {
  const { t } = useLocale();
  const [resending, setResending] = useState(false);
  const [resent, setResent] = useState(false);

  async function handleResend() {
    setResending(true);
    try {
      await api.auth.requestEmailVerification();
      setResent(true);
    } finally {
      setResending(false);
    }
  }

  if (resent) {
    return <p className="mt-2 text-sm text-muted">{t("public.verifyEmail.resendSent")}</p>;
  }

  return (
    <Button type="button" size="sm" loading={resending} className="mt-2" onClick={handleResend}>
      {t("public.verifyEmail.resendButton")}
    </Button>
  );
}

function VerifyEmailRunner({ token }: { token: string }) {
  const { t } = useLocale();
  const { status } = useAuth();
  const [phase, setPhase] = useState<Phase>("verifying");
  const calledRef = useRef(false);

  useEffect(() => {
    // Guards against a double POST on a Strict-Mode dev re-mount -- the token
    // is single-use, so a second call would otherwise surface as token-invalid.
    if (calledRef.current) return;
    calledRef.current = true;

    api.auth
      .verifyEmail({ token })
      .then(() => setPhase("success"))
      .catch((err: unknown) => {
        if (err instanceof ApiError && err.code === "INVALID_OR_EXPIRED_TOKEN") {
          setPhase("token-invalid");
        } else if (err instanceof ApiError && err.status === 429) {
          setPhase("rate-limited");
        } else {
          setPhase("network-error");
        }
      });
  }, [token]);

  if (phase === "verifying") {
    return <LoadingState label={t("public.verifyEmail.verifying")} />;
  }

  if (phase === "success") {
    const isAuthenticated = status === "authenticated";
    return (
      <QuietState
        icon={CheckCircle2}
        title={t("public.verifyEmail.successTitle")}
        body={t("public.verifyEmail.successBody")}
        action={
          <Link
            href={isAuthenticated ? "/dashboard" : "/login"}
            className="mt-2 text-sm text-gold underline-offset-4 hover:underline"
          >
            {isAuthenticated
              ? t("public.verifyEmail.successCtaDashboard")
              : t("public.verifyEmail.successCtaLogin")}
          </Link>
        }
      />
    );
  }

  if (phase === "token-invalid") {
    const isAuthenticated = status === "authenticated";
    return (
      <QuietState
        icon={MailQuestion}
        title={t("public.verifyEmail.invalidTitle")}
        body={
          isAuthenticated
            ? t("public.verifyEmail.invalidBodySignedIn")
            : t("public.verifyEmail.invalidBodySignedOut")
        }
        action={
          isAuthenticated ? (
            <ResendVerification />
          ) : (
            <Link
              href="/login"
              className="mt-2 text-sm text-gold underline-offset-4 hover:underline"
            >
              {t("public.verifyEmail.toLogin")}
            </Link>
          )
        }
      />
    );
  }

  const message =
    phase === "rate-limited" ? t("public.verifyEmail.errorRateLimited") : t("common.networkError");

  return (
    <div
      role="alert"
      className="flex items-start gap-2 rounded-lg border border-danger/30 bg-danger-surface p-3 text-sm text-text"
    >
      <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-danger" aria-hidden="true" />
      <span>{message}</span>
    </div>
  );
}

function MissingToken() {
  const { t } = useLocale();
  return (
    <QuietState
      icon={MailQuestion}
      title={t("public.verifyEmail.missingTokenTitle")}
      body={t("public.verifyEmail.missingTokenBody")}
      action={
        <Link href="/login" className="mt-2 text-sm text-gold underline-offset-4 hover:underline">
          {t("public.verifyEmail.toLogin")}
        </Link>
      }
    />
  );
}

function VerifyEmailGate() {
  const searchParams = useSearchParams();
  const token = searchParams.get("token");
  if (!token) return <MissingToken />;
  return <VerifyEmailRunner token={token} />;
}

export default function VerifyEmailPage() {
  const { t } = useLocale();
  return (
    <div className="sacred-wheel-bg relative flex min-h-screen items-center justify-center overflow-hidden bg-background p-6">
      <NumericWheel className="pointer-events-none absolute -right-24 -top-24 h-96 w-96 opacity-40" />
      <NumericWheel className="pointer-events-none absolute -bottom-32 -left-32 h-96 w-96 opacity-20" />

      <Card className="relative w-full max-w-sm animate-rise-in shadow-elevated">
        <CardHeader className="text-center">
          <CardTitle className="text-2xl">
            <Logo className="justify-center" markClassName="h-10 w-10" textClassName="text-2xl" />
            <span className="sr-only">{t("public.verifyEmail.title")}</span>
          </CardTitle>
        </CardHeader>
        <CardContent>
          <Suspense fallback={<LoadingState label={t("common.loading")} />}>
            <VerifyEmailGate />
          </Suspense>
        </CardContent>
      </Card>
    </div>
  );
}
