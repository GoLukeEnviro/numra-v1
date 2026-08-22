"use client";

import { AppShell } from "@/components/layout/app-shell";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { LinkButton } from "@/components/ui/link-button";
import { Button } from "@/components/ui/button";
import { SecurityCard } from "@/components/settings/security-card";
import { SystemInfoCard } from "@/components/settings/system-info-card";
import { useAuth } from "@/lib/auth-context";
import { useLocale } from "@/i18n/context";
import { SUPPORTED_LOCALES, type Locale } from "@/i18n/catalog";
import { cn } from "@/lib/utils";
import { Database, Languages } from "lucide-react";

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
        </Card>
        <LanguageCard />
        <div className="sm:col-span-2">
          <SecurityCard />
        </div>
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
