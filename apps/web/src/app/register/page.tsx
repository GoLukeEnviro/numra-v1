"use client";

import { api, ApiError } from "@/api/client";
import { Logo } from "@/components/brand/logo";
import { NumericWheel } from "@/components/layout/numeric-wheel";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { LinkButton } from "@/components/ui/link-button";
import { LoadingState } from "@/components/ui/states";
import type { MessageKey } from "@/i18n/catalog";
import { useLocale } from "@/i18n/context";
import { useAuth } from "@/lib/auth-context";
import { useAsync } from "@/lib/use-async";
import { AlertTriangle } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";

const MIN_PASSWORD_LENGTH = 12;

/** Maps a failed register call to a catalog key — never leaks raw server prose. */
function errorKeyFor(err: unknown): MessageKey {
  if (err instanceof ApiError) {
    if (err.status === 409) return "public.register.errorDuplicate";
    if (err.status === 403) return "public.register.errorDisabled";
    if (err.status === 429) return "public.register.errorRateLimited";
    if (err.status === 422) return "public.register.errorValidation";
    if (err.status >= 500) return "public.register.errorServer";
    return "public.register.errorServer";
  }
  return "common.networkError";
}

function RegisterForm() {
  const { register } = useAuth();
  const { t } = useLocale();
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [passwordConfirm, setPasswordConfirm] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<{ code: string; messageKey: MessageKey } | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);

    // Client-side checks mirror the server rules; the server stays authoritative.
    if (password.length < MIN_PASSWORD_LENGTH) {
      setError({ code: "PASSWORD_TOO_SHORT", messageKey: "public.register.errorTooShort" });
      return;
    }
    if (password !== passwordConfirm) {
      setError({ code: "PASSWORD_MISMATCH", messageKey: "public.register.errorMismatch" });
      return;
    }

    setSubmitting(true);
    try {
      await register(email, password);
      router.replace("/onboarding");
    } catch (err) {
      setSubmitting(false);
      setError({
        code: err instanceof ApiError ? err.code : "NETWORK_ERROR",
        messageKey: errorKeyFor(err),
      });
    }
  }

  return (
    <form onSubmit={handleSubmit} noValidate>
      <div className="mb-4">
        <Label htmlFor="email">{t("public.register.email")}</Label>
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
      <div className="mb-4">
        <Label htmlFor="password">{t("public.register.password")}</Label>
        <Input
          id="password"
          name="password"
          type="password"
          autoComplete="new-password"
          minLength={MIN_PASSWORD_LENGTH}
          required
          aria-describedby="password-hint"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
        <p id="password-hint" className="mt-1.5 text-xs text-muted">
          {t("public.register.passwordHint")}
        </p>
      </div>
      <div className="mb-5">
        <Label htmlFor="passwordConfirm">{t("public.register.passwordConfirm")}</Label>
        <Input
          id="passwordConfirm"
          name="passwordConfirm"
          type="password"
          autoComplete="new-password"
          minLength={MIN_PASSWORD_LENGTH}
          required
          value={passwordConfirm}
          onChange={(e) => setPasswordConfirm(e.target.value)}
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
            {t(error.messageKey)}
          </span>
        </div>
      )}

      <Button type="submit" className="w-full" loading={submitting}>
        {t("public.register.submit")}
      </Button>

      <p className="mt-5 text-center text-sm text-muted">
        {t("public.register.haveAccount")}{" "}
        <Link href="/login" className="text-gold underline-offset-4 hover:underline">
          {t("public.landing.navSignIn")}
        </Link>
      </p>
    </form>
  );
}

function SignupClosed() {
  const { t } = useLocale();
  return (
    <div className="text-center">
      <p className="text-sm font-medium text-ivory">{t("public.register.closedTitle")}</p>
      <p className="mt-2 text-sm text-muted">{t("public.register.closedBody")}</p>
      <LinkButton href="/login" className="mt-5">
        {t("public.register.toLogin")}
      </LinkButton>
    </div>
  );
}

export default function RegisterPage() {
  const { t } = useLocale();
  // Public, unauthenticated config: whether this instance accepts self-signup.
  // Until it has loaded there is no functional submit element on the page.
  const configState = useAsync(() => api.publicConfig.get(), []);

  return (
    <div className="sacred-wheel-bg relative flex min-h-screen items-center justify-center overflow-hidden bg-background p-6">
      <NumericWheel className="pointer-events-none absolute -right-24 -top-24 h-96 w-96 opacity-40" />
      <NumericWheel className="pointer-events-none absolute -bottom-32 -left-32 h-96 w-96 opacity-20" />

      <Card className="relative w-full max-w-sm animate-rise-in shadow-elevated">
        <CardHeader className="text-center">
          <h1 className="font-serif text-2xl text-ivory">
            <Logo className="justify-center" markClassName="h-10 w-10" textClassName="text-2xl" />
            <span className="sr-only">{t("public.register.title")}</span>
          </h1>
          <CardDescription>{t("public.register.subtitle")}</CardDescription>
        </CardHeader>
        <CardContent>
          {configState.status === "loading" && (
            <LoadingState label={t("public.register.checkingConfig")} />
          )}
          {/* An unreachable config endpoint must not open a signup form that the
              server would reject anyway — fail closed, offer the login path. */}
          {configState.status === "error" && <SignupClosed />}
          {configState.status === "success" &&
            (configState.data.self_signup_enabled ? <RegisterForm /> : <SignupClosed />)}
        </CardContent>
      </Card>
    </div>
  );
}
