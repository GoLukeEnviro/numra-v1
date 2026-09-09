"use client";

import { api, ApiError } from "@/api/client";
import { Logo } from "@/components/brand/logo";
import { NumericWheel } from "@/components/layout/numeric-wheel";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useLocale } from "@/i18n/context";
import { AlertTriangle, MailCheck } from "lucide-react";
import Link from "next/link";
import { useState, type FormEvent } from "react";

type Phase = "idle" | "submitting" | "submitted";

export default function ForgotPasswordPage() {
  const { t } = useLocale();
  const [email, setEmail] = useState("");
  const [phase, setPhase] = useState<Phase>("idle");
  const [error, setError] = useState<{ code: string; message: string } | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setPhase("submitting");
    try {
      await api.auth.forgotPassword({ email });
      // Deliberately no redirect and no distinction between "known" and
      // "unknown" address here — the request always resolves the same way
      // (anti-enumeration matches the backend's always-202 behavior).
      setPhase("submitted");
    } catch (err) {
      setPhase("idle");
      if (err instanceof ApiError && err.status === 429) {
        setError({ code: err.code, message: t("public.forgotPassword.errorRateLimited") });
      } else {
        setError({ code: "NETWORK_ERROR", message: t("common.networkError") });
      }
    }
  }

  return (
    <div className="sacred-wheel-bg relative flex min-h-screen items-center justify-center overflow-hidden bg-background p-6">
      <NumericWheel className="pointer-events-none absolute -right-24 -top-24 h-96 w-96 opacity-40" />
      <NumericWheel className="pointer-events-none absolute -bottom-32 -left-32 h-96 w-96 opacity-20" />

      <Card className="relative w-full max-w-sm animate-rise-in shadow-elevated">
        <CardHeader className="text-center">
          <CardTitle className="text-2xl">
            <Logo className="justify-center" markClassName="h-10 w-10" textClassName="text-2xl" />
            <span className="sr-only">{t("public.forgotPassword.title")}</span>
          </CardTitle>
          <CardDescription>{t("public.forgotPassword.subtitle")}</CardDescription>
        </CardHeader>
        <CardContent>
          {phase === "submitted" ? (
            <div role="status" className="flex flex-col items-center gap-3 py-4 text-center">
              <MailCheck className="h-6 w-6 text-gold" aria-hidden="true" />
              <p className="text-sm text-text">{t("public.forgotPassword.successBody")}</p>
              <Link href="/login" className="mt-2 text-sm text-gold underline-offset-4 hover:underline">
                {t("public.forgotPassword.backToLogin")}
              </Link>
            </div>
          ) : (
            <form onSubmit={handleSubmit} noValidate>
              <div className="mb-5">
                <Label htmlFor="email">{t("public.forgotPassword.email")}</Label>
                <Input
                  id="email"
                  name="email"
                  type="email"
                  autoComplete="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                />
              </div>

              {error && (
                <div
                  role="alert"
                  className="mb-4 flex items-start gap-2 rounded-lg border border-danger/30 bg-danger-surface p-3 text-sm text-text"
                >
                  <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-danger" aria-hidden="true" />
                  <span>
                    <span className="mr-1.5 rounded bg-black/20 px-1.5 py-0.5 font-mono text-xs">
                      {error.code}
                    </span>
                    {error.message}
                  </span>
                </div>
              )}

              <Button type="submit" className="w-full" loading={phase === "submitting"}>
                {t("public.forgotPassword.submit")}
              </Button>

              <p className="mt-5 text-center text-sm text-muted">
                <Link href="/login" className="text-gold underline-offset-4 hover:underline">
                  {t("public.forgotPassword.backToLogin")}
                </Link>
              </p>
            </form>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
