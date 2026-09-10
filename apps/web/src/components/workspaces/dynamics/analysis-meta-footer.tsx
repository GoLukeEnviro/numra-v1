"use client";

import { useLocale } from "@/i18n/context";

/**
 * Versions/provider footer for a completed analysis — analogous to the Report
 * Reader footer. Rendered verbatim from the result: no derivation.
 */
export function AnalysisMetaFooter({
  result,
}: {
  result: {
    calculation_version: string;
    knowledge_version: string;
    prompt_version: string;
    model_provider: string;
    model_name: string;
  };
}) {
  const { t } = useLocale();
  const rows = [
    { label: t("app.dynamics.meta.calculationVersion"), value: result.calculation_version },
    { label: t("app.dynamics.meta.knowledgeVersion"), value: result.knowledge_version },
    { label: t("app.dynamics.meta.promptVersion"), value: result.prompt_version },
    {
      label: t("app.dynamics.meta.model"),
      value: `${result.model_provider} / ${result.model_name}`,
    },
  ];

  return (
    <dl className="mt-8 grid gap-x-8 gap-y-3 border-t border-white/10 pt-6 text-xs sm:grid-cols-2 lg:grid-cols-4">
      {rows.map((row) => (
        <div key={row.label}>
          <dt className="text-muted">{row.label}</dt>
          <dd className="mt-0.5 font-mono text-text">{row.value}</dd>
        </div>
      ))}
    </dl>
  );
}
