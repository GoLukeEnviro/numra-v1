"use client";

import { useState } from "react";
import { ChevronDown } from "lucide-react";
import type { ThemeStatement } from "@/api/analysis-content";
import { useLocale } from "@/i18n/context";
import { cn } from "@/lib/utils";

/**
 * Collapsible provenance for one `ThemeStatement`. Adapted from
 * `SectionSources` in components/reports/report-reader.tsx, with one deliberate
 * difference: an empty ref group is shown explicitly as "none", never omitted
 * (specs/v2/shadow-dynamics-spec.md — every statement's traceability must be
 * visible, including where a source class was not used).
 */
export function ProvenanceSources({ statement }: { statement: ThemeStatement }) {
  const { t } = useLocale();
  const [open, setOpen] = useState(false);

  const groups: { label: string; refs: string[] }[] = [
    { label: t("app.dynamics.provenance.canonicalLabel"), refs: statement.canonical_refs ?? [] },
    { label: t("app.dynamics.provenance.knowledgeLabel"), refs: statement.knowledge_refs ?? [] },
    {
      label: t("app.dynamics.provenance.workspaceEvidenceLabel"),
      refs: statement.workspace_evidence_refs ?? [],
    },
  ];

  return (
    <div className="mt-4 border-t border-white/10 pt-3">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        className="flex items-center gap-1.5 text-xs text-muted transition-colors hover:text-gold"
      >
        <ChevronDown
          className={cn("h-3.5 w-3.5 transition-transform", open && "rotate-180")}
          aria-hidden="true"
        />
        {open ? t("app.dynamics.provenance.hide") : t("app.dynamics.provenance.show")}
      </button>
      {open && (
        <dl className="mt-3 grid gap-3 text-xs sm:grid-cols-3">
          {groups.map((group) => (
            <div key={group.label}>
              <dt className="text-muted">{group.label}</dt>
              <dd className="mt-1 flex flex-wrap gap-1.5">
                {group.refs.length === 0 ? (
                  <span className="italic text-muted">{t("app.dynamics.provenance.emptyGroup")}</span>
                ) : (
                  group.refs.map((ref) => (
                    <span
                      key={ref}
                      className="rounded bg-surface-2 px-1.5 py-0.5 font-mono text-text"
                    >
                      {ref}
                    </span>
                  ))
                )}
              </dd>
            </div>
          ))}
        </dl>
      )}
    </div>
  );
}
