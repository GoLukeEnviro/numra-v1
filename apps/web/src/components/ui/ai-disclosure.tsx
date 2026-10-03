"use client";

import { Bot } from "lucide-react";
import { useLocale } from "@/i18n/context";
import { cn } from "@/lib/utils";

/**
 * EU AI Act Art. 50(1)/(2) disclosure: a natural person must be told they are
 * interacting with an AI system, and AI-generated content must be labelled as such.
 * `chat` is for live Copilot conversations, `generated` for one-shot output (reports,
 * relationship analysis, shadow dynamics) nobody is actively "talking" to.
 */
export function AiDisclosure({
  variant,
  className,
}: {
  variant: "chat" | "generated";
  className?: string;
}) {
  const { t } = useLocale();
  return (
    <p
      className={cn(
        "flex items-start gap-2 rounded-lg border border-white/10 bg-surface-2 p-3 text-xs leading-5 text-muted",
        className,
      )}
    >
      <Bot className="mt-0.5 h-3.5 w-3.5 shrink-0 text-bronze" aria-hidden="true" />
      <span>{t(variant === "chat" ? "app.ai.disclosureChat" : "app.ai.disclosureGenerated")}</span>
    </p>
  );
}
