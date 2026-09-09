"use client";

import { Suspense, useEffect, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { api, ApiError, type ConnectionInvitationPreviewOut } from "@/api/client";
import { Logo } from "@/components/brand/logo";
import { NumericWheel } from "@/components/layout/numeric-wheel";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { LoadingState } from "@/components/ui/states";
import { useLocale } from "@/i18n/context";
import { useAuth } from "@/lib/auth-context";
import { AlertTriangle, CheckCircle2, MailQuestion } from "lucide-react";

type Phase = "previewing" | "preview-ready" | "token-invalid" | "network-error" | "declined";

/** Ruhiges, seitenlokales Muster fuer erwartete End-States -- wie verify-email/page.tsx. */
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

function formatExpiresIn(iso: string, locale: string): string {
  return new Date(iso).toLocaleString(locale === "de" ? "de-DE" : "en-US", {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

function RedeemRunner({ token }: { token: string }) {
  const { t, locale } = useLocale();
  const { status } = useAuth();
  const router = useRouter();
  const [phase, setPhase] = useState<Phase>("previewing");
  const [preview, setPreview] = useState<ConnectionInvitationPreviewOut | null>(null);
  const [accepting, setAccepting] = useState(false);
  const [declining, setDeclining] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const previewCalledRef = useRef(false);

  useEffect(() => {
    // Guard gegen doppelten Preview-Call bei Strict-Mode-Dev-Remount.
    if (previewCalledRef.current) return;
    previewCalledRef.current = true;

    api.connections
      .previewByToken(token)
      .then((result) => {
        setPreview(result);
        setPhase("preview-ready");
      })
      .catch((err: unknown) => {
        if (err instanceof ApiError) {
          setPhase("token-invalid");
        } else {
          setPhase("network-error");
        }
      });
  }, [token]);

  async function handleAccept() {
    if (accepting || declining) return;
    setAccepting(true);
    setActionError(null);
    try {
      const result = await api.connections.redeemInvitation({ token });
      router.push(`/workspaces/${result.workspace_id}/consent?justConnected=1`);
    } catch {
      setActionError(t("app.connectionsRedeem.acceptError"));
      setAccepting(false);
    }
  }

  async function handleDecline() {
    if (accepting || declining || !preview) return;
    setDeclining(true);
    setActionError(null);
    try {
      await api.connections.declineInvitation(preview.id);
      setPhase("declined");
    } catch {
      setActionError(t("app.connectionsRedeem.declineError"));
    } finally {
      setDeclining(false);
    }
  }

  if (phase === "previewing") {
    return <LoadingState label={t("app.connectionsRedeem.previewing")} />;
  }

  if (phase === "declined") {
    return (
      <QuietState
        icon={CheckCircle2}
        title={t("app.connectionsRedeem.declinedTitle")}
        body={t("app.connectionsRedeem.declinedBody")}
        action={
          <Link href="/dashboard" className="mt-2 text-sm text-gold underline-offset-4 hover:underline">
            {t("app.connectionsRedeem.toDashboard")}
          </Link>
        }
      />
    );
  }

  if (phase === "token-invalid" || phase === "network-error") {
    const body =
      phase === "network-error" ? t("common.networkError") : t("app.connectionsRedeem.invalidBody");
    return (
      <div
        role="alert"
        className="flex items-start gap-2 rounded-lg border border-danger/30 bg-danger-surface p-3 text-sm text-text"
      >
        <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-danger" aria-hidden="true" />
        <span>{body}</span>
      </div>
    );
  }

  if (!preview) return null;
  const isAuthenticated = status === "authenticated";
  const canDecline = preview.method === "EMAIL";

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-col items-center gap-3 py-2 text-center">
        <MailQuestion className="h-6 w-6 text-gold" aria-hidden="true" />
        <p className="text-sm text-ivory">
          <span className="mr-1.5 font-medium">{t("app.connectionsRedeem.methodLabel")}:</span>
          {t(
            preview.method === "LINK"
              ? "app.connections.methodLink"
              : preview.method === "CODE"
                ? "app.connections.methodCode"
                : "app.connections.methodEmail",
          )}
        </p>
        <p className="text-xs text-muted">
          {t("app.connectionsRedeem.expiresIn")} {formatExpiresIn(preview.expires_at, locale)}
        </p>
      </div>

      {actionError && (
        <div
          role="alert"
          className="rounded-lg border border-danger/30 bg-danger-surface p-3 text-sm text-text"
        >
          {actionError}
        </div>
      )}

      {isAuthenticated ? (
        <div className="flex flex-wrap gap-3">
          <Button onClick={handleAccept} loading={accepting} disabled={declining}>
            {t("app.connectionsRedeem.acceptButton")}
          </Button>
          {canDecline && (
            <Button
              variant="secondary"
              onClick={handleDecline}
              loading={declining}
              disabled={accepting}
            >
              {t("app.connectionsRedeem.declineButton")}
            </Button>
          )}
        </div>
      ) : (
        <Link
          href={`/login?next=${encodeURIComponent(`/connections/redeem?token=${token}`)}`}
          className="text-center text-sm text-gold underline-offset-4 hover:underline"
        >
          {t("app.connectionsRedeem.loginCta")}
        </Link>
      )}
    </div>
  );
}

function MissingToken() {
  const { t } = useLocale();
  return (
    <QuietState
      icon={MailQuestion}
      title={t("app.connectionsRedeem.invalidTitle")}
      body={t("app.connectionsRedeem.invalidBody")}
      action={
        <Link href="/dashboard" className="mt-2 text-sm text-gold underline-offset-4 hover:underline">
          {t("app.connectionsRedeem.toDashboard")}
        </Link>
      }
    />
  );
}

function RedeemGate() {
  const searchParams = useSearchParams();
  const token = searchParams.get("token");
  if (!token) return <MissingToken />;
  return <RedeemRunner token={token} />;
}

export default function ConnectionsRedeemPage() {
  const { t } = useLocale();
  return (
    <div className="sacred-wheel-bg relative flex min-h-screen items-center justify-center overflow-hidden bg-background p-6">
      <NumericWheel className="pointer-events-none absolute -right-24 -top-24 h-96 w-96 opacity-40" />
      <NumericWheel className="pointer-events-none absolute -bottom-32 -left-32 h-96 w-96 opacity-20" />

      <Card className="relative w-full max-w-sm animate-rise-in shadow-elevated">
        <CardHeader className="text-center">
          <CardTitle className="text-2xl">
            <Logo className="justify-center" markClassName="h-10 w-10" textClassName="text-2xl" />
            <span className="sr-only">{t("app.connectionsRedeem.title")}</span>
          </CardTitle>
        </CardHeader>
        <CardContent>
          <Suspense fallback={<LoadingState label={t("common.loading")} />}>
            <RedeemGate />
          </Suspense>
        </CardContent>
      </Card>
    </div>
  );
}
