"use client";

import { StatusPage } from "@/components/layout/status-page";
import { PublicFooter } from "@/components/layout/public-footer";
import { LinkButton } from "@/components/ui/link-button";
import { useLocale } from "@/i18n/context";

/**
 * Branded, localised 404 for every unmatched route (replaces Next's default).
 * Carries `PublicFooter` because a dead end is still a public, session-less page
 * and § 5 DDG requires Impressum to stay reachable from it.
 */
export default function NotFound() {
  const { t } = useLocale();
  return (
    <StatusPage
      eyebrow={t("public.notFound.eyebrow")}
      title={t("public.notFound.title")}
      body={t("public.notFound.body")}
      footer={<PublicFooter />}
    >
      <LinkButton href="/" size="lg">
        {t("public.notFound.cta")}
      </LinkButton>
    </StatusPage>
  );
}
