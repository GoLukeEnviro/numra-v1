import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { METRIC_LABELS } from "@/components/relationships/comparison-table";
import type { RelationshipMetricKey } from "@/api/canonical-profile";
import type { RelationshipInsightOut } from "@/api/client";
import { useLocale } from "@/i18n/context";
import { Sparkles } from "lucide-react";

/**
 * V1.5 Epic F: structured, knowledge-sourced qualitative notes -- one card per
 * metric, each theme quoted directly from the knowledge package (never generated,
 * never scored). There is deliberately no numeric summary anywhere on this
 * component: see the disclaimer directly above it on the detail page.
 */
export function RelationshipInsights({
  insights,
  labelA,
  labelB,
}: {
  insights: readonly RelationshipInsightOut[];
  labelA: string;
  labelB: string;
}) {
  const { t } = useLocale();
  if (insights.length === 0) return null;

  return (
    <Card className="mb-6">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Sparkles className="h-4 w-4 text-gold" aria-hidden="true" />
          {t("app.relationshipDetail.notesTitle")}
        </CardTitle>
        <CardDescription>{t("app.relationshipDetail.notesBody")}</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="grid gap-4 sm:grid-cols-2">
          {insights.map((insight) => (
            <div
              key={insight.metric_id}
              className="rounded-lg border border-white/10 bg-surface-2 p-4"
            >
              <div className="mb-2 flex items-center justify-between">
                <p className="text-sm font-medium text-ivory">
                  {METRIC_LABELS[insight.metric_id as RelationshipMetricKey] ?? insight.metric_id}
                </p>
                {insight.shared_number && (
                  <span className="rounded-full bg-gold/10 px-2 py-0.5 text-[11px] text-gold">
                    {t("app.relationshipDetail.sameNumber")}
                  </span>
                )}
              </div>
              <div className="space-y-3 text-sm text-text">
                <div>
                  <p className="mb-1 text-xs text-muted">
                    {labelA} · {insight.person_a_number}
                  </p>
                  <ul className="list-disc space-y-1 pl-4">
                    {insight.person_a_relationship_themes.map((theme) => (
                      <li key={theme}>{theme}</li>
                    ))}
                  </ul>
                </div>
                <div>
                  <p className="mb-1 text-xs text-muted">
                    {labelB} · {insight.person_b_number}
                  </p>
                  <ul className="list-disc space-y-1 pl-4">
                    {insight.person_b_relationship_themes.map((theme) => (
                      <li key={theme}>{theme}</li>
                    ))}
                  </ul>
                </div>
              </div>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
