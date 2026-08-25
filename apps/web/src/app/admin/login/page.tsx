"use client";

import { ApiError } from "@/api/client";
import { Logo } from "@/components/brand/logo";
import { NumericWheel } from "@/components/layout/numeric-wheel";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { LinkButton } from "@/components/ui/link-button";
import { LoadingState } from "@/components/ui/states";
import { useLocale } from "@/i18n/context";
import { useAuth } from "@/lib/auth-context";
import { AlertTriangle, ShieldCheck } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";

/**
 * A separate entrance to the console — not a separate auth system. It posts to the
 * very same `/v1/auth/login` through `useAuth().login()`, so there is one session
 * cookie, one CSRF token and one server-side notion of who is signed in.
 *
 * Whether an address belongs to an administrator is never revealed before
 * authentication: the credential error is byte-identical to the one `/login` shows,
 * and the admin/non-admin distinction is only made *after* a successful sign-in.
 */
export default function AdminLoginPage() {
  const { status, user, login } = useAuth();
  const router = useRouter();
  const { t } = useLocale();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<{ code: string; message: string } | null>(null);

  const isAdmin = status === "authenticated" && user?.role === "ADMIN";

  useEffect(() => {
    if (isAdmin) router.replace("/admin");
  }, [isAdmin, router]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await login(email, password);
      // No navigation here: the effect above redirects once the session is known to
      // be an admin one. A USER lands on the "no admin rights" panel below and stays
      // signed in — being a non-admin is not a reason to destroy their session.
    } catch (err) {
      if (err instanceof ApiError) {
        setError({ code: err.code, message: err.message });
      } else {
        setError({ code: "NETWORK_ERROR", message: t("admin.login.networkError") });
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="sacred-wheel-bg relative flex min-h-screen items-center justify-center overflow-hidden bg-background p-6">
      <NumericWheel className="pointer-events-none absolute -right-24 -top-24 h-96 w-96 opacity-40" />

      <Card className="relative w-full max-w-sm animate-rise-in shadow-elevated">
        <h1 className="sr-only">{t("admin.login.title")}</h1>
        <CardHeader className="text-center">
          <CardTitle className="text-2xl">
            <Logo className="justify-center" markClassName="h-10 w-10" textClassName="text-2xl" />
            <span className="mt-3 flex items-center justify-center gap-1.5 text-sm text-gold">
              <ShieldCheck className="h-4 w-4" aria-hidden="true" />
              {t("admin.login.title")}
            </span>
          </CardTitle>
          <CardDescription>{t("admin.login.subtitle")}</CardDescription>
        </CardHeader>
        <CardContent>
          {status === "checking" && <LoadingState label={t("admin.guard.checking")} />}

          {/* `isAdmin` renders nothing — the effect above is already navigating to /admin. */}

          {status === "authenticated" && !isAdmin && (
            <div className="flex flex-col items-start gap-3">
              <h2 className="font-serif text-lg text-ivory">{t("admin.login.notAdminTitle")}</h2>
              <p role="status" className="text-sm text-text">
                {t("admin.login.notAdminBody")}
              </p>
              <LinkButton href="/dashboard" variant="secondary" size="sm">
                {t("admin.guard.backToDashboard")}
              </LinkButton>
            </div>
          )}

          {status === "anonymous" && (
            <form onSubmit={handleSubmit} noValidate>
              <div className="mb-4">
                <Label htmlFor="admin-email">{t("admin.login.email")}</Label>
                <Input
                  id="admin-email"
                  name="email"
                  type="email"
                  autoComplete="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                />
              </div>
              <div className="mb-5">
                <Label htmlFor="admin-password">{t("admin.login.password")}</Label>
                <Input
                  id="admin-password"
                  name="password"
                  type="password"
                  autoComplete="current-password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                />
              </div>

              {error && (
                <div
                  role="alert"
                  className="mb-4 flex items-start gap-2 rounded-lg border border-danger/30 bg-danger-surface p-3 text-sm text-text"
                >
                  <AlertTriangle
                    className="mt-0.5 h-4 w-4 shrink-0 text-danger"
                    aria-hidden="true"
                  />
                  <span>
                    <span className="mr-1.5 rounded bg-black/20 px-1.5 py-0.5 font-mono text-xs">
                      {error.code}
                    </span>
                    {error.message}
                  </span>
                </div>
              )}

              <Button type="submit" className="w-full" loading={submitting}>
                {t("admin.login.submit")}
              </Button>
              <p className="mt-4 text-center text-xs text-muted">{t("admin.login.hint")}</p>
            </form>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
