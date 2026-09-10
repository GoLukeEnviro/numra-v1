"use client";

import type { ReactNode } from "react";
import { Badge } from "@/components/ui/badge";
import type { ShadowDynamicsResult, ThemeStatement } from "@/api/analysis-content";
import { humanizeSnakeCase } from "@/lib/analysis-status";
import { splitParagraphs } from "@/lib/prose";
import { useLocale } from "@/i18n/context";
import type { MessageKey } from "@/i18n/catalog";
import { ProvenanceSources } from "@/components/workspaces/dynamics/provenance-sources";
import { AnalysisMetaFooter } from "@/components/workspaces/dynamics/analysis-meta-footer";

const INTENSITY_LABEL_KEYS: Record<string, MessageKey> = {
  low: "app.dynamics.intensity.low",
  moderate: "app.dynamics.intensity.moderate",
  high: "app.dynamics.intensity.high",
};

function Statement({ statement }: { statement: ThemeStatement }) {
  return (
    <div>
      <div className="report-prose">
        {splitParagraphs(statement.text).map((paragraph, i) => (
          <p key={i}>{paragraph}</p>
        ))}
      </div>
      <ProvenanceSources statement={statement} />
    </div>
  );
}

function Block({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="max-w-reading">
      <h3 className="font-serif text-lg text-ivory">{title}</h3>
      <div className="mt-3 flex flex-col gap-6">{children}</div>
    </section>
  );
}

/**
 * Completed Shadow Dynamics: all seven result fields.
 *
 * Two hard rules from specs/v2/shadow-dynamics-spec.md:
 *  - `pattern_intensity` is a coarse label, shown ONLY as translated text — never a
 *    number, bar, percentage or `role="progressbar"`.
 *  - Shadow themes use neutral "Person A" / "Person B" labels: `user_a`/`user_b` in
 *    the stored snapshot carry no member identity, so mapping them to display names
 *    would risk attributing the wrong shadow themes to someone.
 */
export function ShadowDynamicsView({ result }: { result: ShadowDynamicsResult }) {
  const { t } = useLocale();
  const intensityKey = INTENSITY_LABEL_KEYS[result.pattern_intensity.toLowerCase()];
  const intensityText = intensityKey ? t(intensityKey) : humanizeSnakeCase(result.pattern_intensity);

  return (
    <div className="animate-fade-in flex flex-col gap-8">
      <Block title={t("app.dynamics.shadow.personA")}>
        {result.user_a_shadow_themes.map((s, i) => (
          <Statement key={i} statement={s} />
        ))}
      </Block>

      <Block title={t("app.dynamics.shadow.personB")}>
        {result.user_b_shadow_themes.map((s, i) => (
          <Statement key={i} statement={s} />
        ))}
      </Block>

      <Block title={t("app.dynamics.shadow.interactionPattern")}>
        <Statement statement={result.interaction_pattern} />
      </Block>

      <Block title={t("app.dynamics.shadow.escalationLoop")}>
        <Statement statement={result.escalation_loop} />
      </Block>

      <Block title={t("app.dynamics.shadow.deescalation")}>
        {result.deescalation_opportunities.map((s, i) => (
          <Statement key={i} statement={s} />
        ))}
      </Block>

      <section className="max-w-reading">
        <h3 className="font-serif text-lg text-ivory">{t("app.dynamics.shadow.intensityTitle")}</h3>
        <p className="mt-2 text-sm text-muted">
          {t("app.dynamics.shadow.intensityLabel")}{" "}
          <Badge variant="neutral">{intensityText}</Badge>
        </p>
      </section>

      <section className="max-w-reading">
        <h3 className="font-serif text-lg text-ivory">{t("app.dynamics.shadow.microTasksTitle")}</h3>
        <p className="mt-2 text-xs text-muted">{t("app.dynamics.shadow.microTasksHint")}</p>
        <ul className="mt-3 list-disc pl-5 text-sm text-text">
          {result.recommended_micro_tasks.map((task, i) => (
            <li key={i} className="mt-1">
              {task}
            </li>
          ))}
        </ul>
      </section>

      <AnalysisMetaFooter result={result} />
    </div>
  );
}
