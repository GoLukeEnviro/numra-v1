"use client";

import { StatusPage } from "@/components/layout/status-page";
import { Button } from "@/components/ui/button";
import { LinkButton } from "@/components/ui/link-button";
import { useLocale } from "@/i18n/context";

/**
 * Route-level error boundary: a render error anywhere below the root layout lands
 * here instead of blanking the page. The error message is never shown — it can
 * carry internal detail — only Next's opaque digest, so a report can be matched to
 * the server log.
 */
export default function RouteError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  const { t } = useLocale();
  return (
    <StatusPage title={t("public.error.title")} body={t("public.error.body")}>
      <Button size="lg" onClick={reset}>
        {t("public.error.retry")}
      </Button>
      <LinkButton href="/" variant="secondary" size="lg">
        {t("public.error.home")}
      </LinkButton>
      {error.digest && (
        <p className="w-full pt-4 font-mono text-xs text-muted">
          {t("public.error.reference")}: {error.digest}
        </p>
      )}
    </StatusPage>
  );
}
