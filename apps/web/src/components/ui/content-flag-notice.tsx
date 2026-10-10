"use client";

import type { ReactNode } from "react";
import { AlertTriangle } from "lucide-react";
import { useLocale } from "@/i18n/context";
import { cn } from "@/lib/utils";

/**
 * D6: shown above a stored text the server flagged (`content_flag`). The text itself stays
 * visible and unchanged -- the notice only says that it must not be taken as reliable and
 * that the original is kept. `action` carries the explicit "regenerate" control.
 */
export function ContentFlagNotice({
  flag,
  action,
  className,
}: {
  flag: string | undefined;
  action?: ReactNode;
  className?: string;
}) {
  const { t } = useLocale();
  if (!flag || flag === "none") return null;
  return (
    <div
      role="note"
      data-testid="content-flag-notice"
      className={cn(
        "flex flex-col gap-3 rounded-lg border border-gold/40 bg-gold/10 p-4 text-sm text-text",
        className,
      )}
    >
      <div className="flex items-start gap-3">
        <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-gold" aria-hidden="true" />
        <div>
          <p className="font-medium text-ivory">{t("app.contentFlag.title")}</p>
          <p className="mt-1 leading-relaxed text-muted">{t("app.contentFlag.body")}</p>
        </div>
      </div>
      {action}
    </div>
  );
}
