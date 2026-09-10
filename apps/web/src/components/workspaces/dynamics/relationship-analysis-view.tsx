"use client";

import { Badge } from "@/components/ui/badge";
import type { RelationshipAnalysisResult } from "@/api/analysis-content";
import { humanizeSnakeCase } from "@/lib/analysis-status";
import { splitParagraphs } from "@/lib/prose";
import { useLocale } from "@/i18n/context";
import { dimensionLabel } from "@/components/workspaces/dynamics/dimension-label";
import { ProvenanceSources } from "@/components/workspaces/dynamics/provenance-sources";
import { AnalysisMetaFooter } from "@/components/workspaces/dynamics/analysis-meta-footer";

/**
 * Completed Relationship Analysis: one block per frame dimension, each statement
 * shown with its full, always-visible provenance. Renders exactly what the API
 * returned — no text is generated, shortened or re-ordered, and there is no
 * compatibility score anywhere.
 */
export function RelationshipAnalysisView({ result }: { result: RelationshipAnalysisResult }) {
  const { t } = useLocale();

  return (
    <div className="animate-fade-in">
      <div className="flex flex-wrap items-center gap-2">
        <Badge variant="master">{humanizeSnakeCase(result.relationship_type)}</Badge>
        <Badge variant="neutral">
          {result.dimensions.length} {t("app.dynamics.relationship.dimensionsLabel")}
        </Badge>
      </div>

      <div className="mt-6 flex flex-col gap-8">
        {result.dimensions.map((dimension) => (
          <section key={dimension.dimension_id} className="max-w-reading">
            <h3 className="font-serif text-lg text-ivory">
              {dimensionLabel(dimension.dimension_id, t)}
            </h3>
            {dimension.statements.map((statement, index) => (
              <div key={index} className="mt-3">
                <div className="report-prose">
                  {splitParagraphs(statement.text).map((paragraph, i) => (
                    <p key={i}>{paragraph}</p>
                  ))}
                </div>
                <ProvenanceSources statement={statement} />
              </div>
            ))}
          </section>
        ))}
      </div>

      <AnalysisMetaFooter result={result} />
    </div>
  );
}
