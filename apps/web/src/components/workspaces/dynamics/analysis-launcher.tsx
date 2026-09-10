"use client";

import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/states";
import { useLocale } from "@/i18n/context";
import type { MessageKey } from "@/i18n/catalog";
import { Sparkles } from "lucide-react";

/**
 * The "no analysis yet" prompt: an explanatory line plus a single Start button.
 * `POST` (and its per-attempt Idempotency-Key) lives in `useAnalysisProgress`; this
 * only calls `onLaunch`.
 */
export function AnalysisLauncher({
  titleKey,
  bodyKey,
  ctaKey,
  ctaBusyKey,
  onLaunch,
  launching,
}: {
  titleKey: MessageKey;
  bodyKey: MessageKey;
  ctaKey: MessageKey;
  ctaBusyKey: MessageKey;
  onLaunch: () => void;
  launching: boolean;
}) {
  const { t } = useLocale();
  return (
    <EmptyState
      title={t(titleKey)}
      description={t(bodyKey)}
      action={
        <Button className="mt-2" onClick={onLaunch} loading={launching}>
          <Sparkles className="h-4 w-4" aria-hidden="true" />
          {launching ? t(ctaBusyKey) : t(ctaKey)}
        </Button>
      }
    />
  );
}
