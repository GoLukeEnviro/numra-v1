"use client";

import { ApiError } from "@/api/client";
import { Logo } from "@/components/brand/logo";
import { NumericWheel } from "@/components/layout/numeric-wheel";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import type { MessageKey } from "@/i18n/catalog";
import { useLocale } from "@/i18n/context";
import { useAuth } from "@/lib/auth-context";
import { AlertTriangle } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";

const PROMISE_KEYS: MessageKey[] = [
  "public.login.promise1",
  "public.login.promise2",
  "public.login.promise3",
];

export default function LoginPage() {
  const { login } = useAuth();
  const { t } = useLocale();
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<{ code: string; message: string } | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await login(email, password);
      router.push("/dashboard");
    } catch (err) {
      if (err instanceof ApiError) {
        setError({ code: err.code, message: err.message });
      } else {
        setError({ code: "NETWORK_ERROR", message: t("common.networkError") });
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="sacred-wheel-bg relative flex min-h-screen items-center justify-center overflow-hidden bg-background p-6">
      <NumericWheel className="pointer-events-none absolute -right-24 -top-24 h-96 w-96 opacity-40" />
      <NumericWheel className="pointer-events-none absolute -bottom-32 -left-32 h-96 w-96 opacity-20" />

      <div className="relative flex w-full max-w-4xl flex-col items-center gap-12 lg:flex-row lg:items-center lg:justify-between">
        {/* Brand panel — hidden on small screens so the form stays the whole viewport. */}
        <div className="hidden max-w-sm animate-rise-in lg:block">
          <h1 className="mt-0">
            <Logo markClassName="h-14 w-14" textClassName="text-4xl" />
          </h1>
          <p className="mt-6 text-sm leading-relaxed text-muted">{t("public.login.brandIntro")}</p>
          <ul className="mt-8 flex flex-col gap-3">
            {PROMISE_KEYS.map((key) => (
              <li key={key} className="flex gap-3 text-sm text-text">
                <span
                  aria-hidden="true"
                  className="mt-[0.45rem] h-1.5 w-1.5 shrink-0 rounded-full bg-gold"
                />
                {t(key)}
              </li>
            ))}
          </ul>
        </div>

        <Card className="w-full max-w-sm animate-rise-in shadow-elevated">
          <CardHeader className="text-center">
            <CardTitle className="text-2xl">
              <Logo
                className="justify-center lg:hidden"
                markClassName="h-10 w-10"
                textClassName="text-2xl"
              />
              <span className="hidden lg:inline">Numra</span>
            </CardTitle>
            <CardDescription>{t("public.login.subtitle")}</CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit} noValidate>
              <div className="mb-4">
                <Label htmlFor="email">{t("public.login.email")}</Label>
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
              <div className="mb-5">
                <Label htmlFor="password">{t("public.login.password")}</Label>
                <Input
                  id="password"
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
                {t("public.login.submit")}
              </Button>

              <p className="mt-5 text-center text-sm text-muted">
                {t("public.login.noAccount")}{" "}
                <Link href="/register" className="text-gold underline-offset-4 hover:underline">
                  {t("public.login.createAccount")}
                </Link>
              </p>
            </form>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
