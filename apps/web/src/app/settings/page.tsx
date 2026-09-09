"use client";

import { AppShell } from "@/components/layout/app-shell";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { LinkButton } from "@/components/ui/link-button";
import { Button } from "@/components/ui/button";
import { EntitlementsCard } from "@/components/settings/entitlements-card";
import { SecurityCard } from "@/components/settings/security-card";
import { SystemInfoCard } from "@/components/settings/system-info-card";
import { api } from "@/api/client";
import { useAuth } from "@/lib/auth-context";
import { useLocale } from "@/i18n/context";
import { SUPPORTED_LOCALES, type Locale } from "@/i18n/catalog";
import { cn } from "@/lib/utils";
import { BadgeCheck, Database, Languages } from "lucide-react";
import { useState } from "react";

const LOCALE_LABEL_KEY: Record<Locale, "settings.languageGerman" | "settings.languageEnglish"> = {
  de: "settings.languageGerman",
  en: "settings.languageEnglish",
};

function LanguageCard() {
  const { locale, setLocale, t } = useLocale();

  return (
    <Card>
      <CardHeader>
        <div className="mb-1 flex items-center gap-2">
          <Languages className="h-5 w-5 text-gold" aria-hidden="true" />
          <CardTitle className="text-base">{t("settings.language")}</CardTitle>
        </div>
        <CardDescription>{t("settings.languageDescription")}</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="flex gap-2" role="group" aria-label={t("settings.language")}>
          {SUPPORTED_LOCALES.map((option) => (
            <Button
              key={option}
              type="button"
              variant={option === locale ? "primary" : "secondary"}
              size="sm"
              aria-pressed={option === locale}
              onClick={() => setLocale(option)}
              className={cn(option === locale && "pointer-events-none")}
            >
              {t(LOCALE_LABEL_KEY[option])}
            </Button>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}

function EmailVerificationStatus() {
  const { t } = useLocale();
  const { user } = useAuth();
  const [resending, setResending] = useState(false);
  const [resent, setResent] = useState(false);

  if (user?.email_verified_at != null) {
    return (
      <span className="inline-flex items-center gap-1.5 rounded-full bg-success/10 px-2.5 py-1 text-xs text-success">
        <BadgeCheck className="h-3.5 w-3.5" aria-hidden="true" />
        {t("app.account.emailVerified")}
      </span>
    );
  }

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
    <div className="mt-2">
      <p className="text-xs text-muted">{t("app.account.emailUnverifiedBody")}</p>
      {resent ? (
        <p className="mt-1.5 text-xs text-gold">{t("app.account.resendVerificationSent")}</p>
      ) : (
        <Button type="button" size="sm" variant="secondary" className="mt-2" loading={resending} onClick={handleResend}>
          {t("app.account.resendVerification")}
        </Button>
      )}
    </div>
  );
}

function SettingsContent() {
  const { user } = useAuth();
  const { t } = useLocale();

  return (
    <div>
      <div className="mb-8">
        <h1 className="font-serif text-3xl text-ivory">{t("settings.title")}</h1>
      </div>
      <div className="grid gap-4 sm:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">{t("settings.account")}</CardTitle>
            <CardDescription>{user?.email ?? "—"}</CardDescription>
          </CardHeader>
          <CardContent>
            <EmailVerificationStatus />
          </CardContent>
        </Card>
        <LanguageCard />
        <div className="sm:col-span-2">
          <SecurityCard />
        </div>
        <EntitlementsCard />
        <Card>
          <CardHeader>
            <div className="mb-1 flex items-center gap-2">
              <Database className="h-5 w-5 text-gold" aria-hidden="true" />
              <CardTitle className="text-base">{t("settings.privacyData")}</CardTitle>
            </div>
            <CardDescription>{t("settings.privacyDataDescription")}</CardDescription>
          </CardHeader>
          <CardContent>
            <LinkButton href="/settings/privacy" variant="secondary" size="sm">
              {t("settings.viewPrivacySettings")}
            </LinkButton>
          </CardContent>
        </Card>
        <SystemInfoCard />
      </div>
    </div>
  );
}

export default function SettingsPage() {
  return (
    <AppShell>
      <SettingsContent />
    </AppShell>
  );
}
