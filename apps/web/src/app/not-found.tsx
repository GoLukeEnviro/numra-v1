"use client";

import { StatusPage } from "@/components/layout/status-page";
import { LinkButton } from "@/components/ui/link-button";
import { useLocale } from "@/i18n/context";

/** Branded, localised 404 for every unmatched route (replaces Next's default). */
export default function NotFound() {
  const { t } = useLocale();
  return (
    <StatusPage
      eyebrow={t("public.notFound.eyebrow")}
      title={t("public.notFound.title")}
      body={t("public.notFound.body")}
    >
      <LinkButton href="/" size="lg">
        {t("public.notFound.cta")}
      </LinkButton>
    </StatusPage>
  );
}
