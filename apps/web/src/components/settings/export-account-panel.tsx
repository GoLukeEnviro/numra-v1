"use client";

import { api } from "@/api/client";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { buttonVariants } from "@/components/ui/button";
import { useLocale } from "@/i18n/context";
import { cn } from "@/lib/utils";
import { Download, ShieldCheck } from "lucide-react";

/**
 * Account-data export (PWA-07).
 *
 * Deliberately a plain `<a href>` to the same-origin API proxy rather than a fetch:
 * `GET /v1/account/export` answers with `application/json` plus a
 * `Content-Disposition: attachment` filename, so the browser performs the download —
 * no blob plumbing in the component, and the file arrives with the server's own
 * (timestamped, versioned) name.
 *
 * It sits above the deletion panel on purpose: the export is the copy you take
 * *before* deleting, and the deletion copy points at exactly that.
 */
export function ExportAccountPanel() {
  const { t } = useLocale();

  return (
    <Card className="mb-4">
      <CardHeader>
        <div className="flex items-center gap-2">
          <Download className="h-5 w-5 text-gold" aria-hidden="true" />
          <CardTitle className="text-base">{t("app.exportData.title")}</CardTitle>
        </div>
        <CardDescription>{t("app.exportData.body")}</CardDescription>
      </CardHeader>
      <CardContent>
        <p className="flex items-start gap-2 rounded-lg border border-white/10 bg-black/20 p-3 text-sm leading-6 text-text">
          <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-success" aria-hidden="true" />
          <span>{t("app.exportData.includes")}</span>
        </p>
        <p className="mt-3 text-xs text-muted">{t("app.exportData.hint")}</p>
        <a
          href={api.account.exportUrl()}
          download
          className={cn(buttonVariants({ variant: "secondary" }), "mt-4")}
        >
          <Download className="h-4 w-4" aria-hidden="true" />
          {t("app.exportData.action")}
        </a>
      </CardContent>
    </Card>
  );
}
