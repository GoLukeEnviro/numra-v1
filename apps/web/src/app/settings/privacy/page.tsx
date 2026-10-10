"use client";

import { AppShell } from "@/components/layout/app-shell";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { DeleteAccountPanel } from "@/components/settings/delete-account-panel";
import { ExportAccountPanel } from "@/components/settings/export-account-panel";
import { useLocale } from "@/i18n/context";
import Link from "next/link";

function PrivacyContent() {
  const { t } = useLocale();
  return (
    <div className="max-w-2xl">
      <div className="mb-8">
        <h1 className="font-serif text-3xl text-ivory">{t("app.privacy.title")}</h1>
        <p className="mt-1 text-sm text-muted">{t("app.privacy.subtitle")}</p>
        <Link href="/datenschutz" className="mt-2 inline-block text-sm text-gold underline-offset-4 hover:underline">
          {t("public.legal.fullPrivacyPolicy")}
        </Link>
      </div>

      <Card className="mb-4">
        <CardHeader>
          <CardTitle className="text-base">{t("app.privacy.storedTitle")}</CardTitle>
        </CardHeader>
        <CardContent>
          <ul className="list-disc space-y-2 pl-5 text-sm text-text">
            <li>
              <strong className="text-ivory">{t("app.privacy.storedProfiles")}</strong>{" "}
              {t("app.privacy.storedProfilesBody")}
            </li>
            <li>
              <strong className="text-ivory">{t("app.privacy.storedCalculations")}</strong>{" "}
              {t("app.privacy.storedCalculationsBody")}{" "}
              <code className="mx-1 rounded bg-black/20 px-1 py-0.5 font-mono text-xs">
                as_of_date
              </code>
            </li>
            <li>
              <strong className="text-ivory">{t("app.privacy.storedRelationships")}</strong>{" "}
              {t("app.privacy.storedRelationshipsBody")}
            </li>
            <li>
              <strong className="text-ivory">{t("app.privacy.storedReports")}</strong>{" "}
              {t("app.privacy.storedReportsBody")}
            </li>
            <li>
              <strong className="text-ivory">{t("app.privacy.storedAccount")}</strong>{" "}
              {t("app.privacy.storedAccountBody")}
            </li>
          </ul>
        </CardContent>
      </Card>

      <Card className="mb-4">
        <CardHeader>
          <CardTitle className="text-base">{t("app.privacy.neverTitle")}</CardTitle>
        </CardHeader>
        <CardContent>
          <ul className="list-disc space-y-2 pl-5 text-sm text-text">
            <li>{t("app.privacy.neverScore")}</li>
            <li>{t("app.privacy.neverDiagnosis")}</li>
            <li>{t("app.privacy.neverBirthTime")}</li>
          </ul>
        </CardContent>
      </Card>

      {/* Export liegt bewusst VOR dem Löschen: die Kopie nimmt man vorher mit. */}
      <ExportAccountPanel />

      <Card className="mb-4">
        <CardHeader>
          <CardTitle className="text-base">{t("app.privacy.deleteOneTitle")}</CardTitle>
          <CardDescription>{t("app.privacy.deleteOneBody")}</CardDescription>
        </CardHeader>
      </Card>

      <DeleteAccountPanel />
    </div>
  );
}

export default function PrivacySettingsPage() {
  return (
    <AppShell>
      <PrivacyContent />
    </AppShell>
  );
}
