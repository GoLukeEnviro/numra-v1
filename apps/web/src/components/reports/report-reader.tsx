"use client";

import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { NumericWheel } from "@/components/layout/numeric-wheel";
import type { ReportOut } from "@/api/client";
import {
  orderedSections,
  type StructuredReport,
  type StructuredReportSection,
} from "@/api/report-content";
import { describeReportType } from "@/lib/report-status";
import { splitParagraphs } from "@/lib/prose";
import { formatDateTime, cn } from "@/lib/utils";
import { ChevronDown } from "lucide-react";

function sectionAnchor(sectionId: string): string {
  return `section-${sectionId}`;
}

/**
 * V1.5 Epic M: which CanonicalProfile metrics and which knowledge/ entries this
 * section was actually grounded in -- taken verbatim from the manifest the pipeline
 * used, never inferred from the prose. Absent (both arrays empty/undefined) on
 * reports generated before this field existed, in which case nothing renders.
 */
function SectionSources({ section }: { section: StructuredReportSection }) {
  const [open, setOpen] = useState(false);
  const metricRefs = section.metric_refs ?? [];
  const knowledgeRefs = section.knowledge_refs ?? [];
  if (metricRefs.length === 0 && knowledgeRefs.length === 0) return null;

  return (
    <div className="mt-5 border-t border-white/10 pt-4">
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
        {open ? "Hide sources" : "Sources"}
      </button>
      {open && (
        <dl className="mt-3 grid gap-3 text-xs sm:grid-cols-2">
          {metricRefs.length > 0 && (
            <div>
              <dt className="text-muted">Profile metrics</dt>
              <dd className="mt-1 flex flex-wrap gap-1.5">
                {metricRefs.map((ref) => (
                  <span
                    key={ref}
                    className="rounded bg-surface-2 px-1.5 py-0.5 font-mono text-text"
                  >
                    {ref}
                  </span>
                ))}
              </dd>
            </div>
          )}
          {knowledgeRefs.length > 0 && (
            <div>
              <dt className="text-muted">Knowledge entries</dt>
              <dd className="mt-1 flex flex-wrap gap-1.5">
                {knowledgeRefs.map((ref) => (
                  <span
                    key={ref}
                    className="rounded bg-surface-2 px-1.5 py-0.5 font-mono text-text"
                  >
                    {ref}
                  </span>
                ))}
              </dd>
            </div>
          )}
        </dl>
      )}
    </div>
  );
}

/**
 * Long-form reading surface for a completed report.
 *
 * Renders exactly what the API returned: section titles, section text and the
 * provenance fields recorded with the report. No text is generated, shortened,
 * re-ordered beyond `order_index`, or supplemented client-side.
 */
export function ReportReader({
  report,
  content,
}: {
  report: ReportOut;
  content: StructuredReport;
}) {
  const sections = orderedSections(content);

  return (
    <article className="animate-fade-in">
      <header className="relative overflow-hidden rounded-xl border border-white/10 bg-surface p-8 shadow-elevated sm:p-10">
        <NumericWheel className="pointer-events-none absolute -right-20 -top-20 h-72 w-72 opacity-[0.14]" />
        <div className="relative">
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant="master">{describeReportType(report.report_type)}</Badge>
            <Badge variant="neutral">{content.language.toUpperCase()}</Badge>
          </div>
          <h1 className="mt-5 font-serif text-3xl text-ivory sm:text-4xl">
            {describeReportType(report.report_type)} reading
          </h1>
          <p className="mt-3 max-w-reading text-sm leading-relaxed text-muted">
            {sections.length} section{sections.length === 1 ? "" : "s"} ·{" "}
            {content.total_word_count.toLocaleString()} words · generated{" "}
            {formatDateTime(report.generated_at)}
          </p>

          <dl className="mt-8 grid gap-x-8 gap-y-3 border-t border-white/10 pt-6 text-xs sm:grid-cols-2 lg:grid-cols-4">
            <div>
              <dt className="text-muted">Calculation version</dt>
              <dd className="mt-0.5 font-mono text-text">{content.calculation_version}</dd>
            </div>
            <div>
              <dt className="text-muted">Knowledge version</dt>
              <dd className="mt-0.5 font-mono text-text">{content.knowledge_version}</dd>
            </div>
            <div>
              <dt className="text-muted">Prompt version</dt>
              <dd className="mt-0.5 font-mono text-text">{content.prompt_version}</dd>
            </div>
            <div>
              <dt className="text-muted">Language model</dt>
              <dd className="mt-0.5 font-mono text-text">
                {content.model_provider} / {content.model_name}
              </dd>
            </div>
          </dl>
        </div>
      </header>

      <div className="mt-10 gap-12 lg:flex lg:items-start">
        <nav
          aria-label="Report sections"
          className="mb-8 shrink-0 lg:sticky lg:top-10 lg:mb-0 lg:w-52"
        >
          <p className="mb-3 text-xs uppercase tracking-wider text-muted">Contents</p>
          <ol className="flex flex-col gap-1.5 text-sm">
            {sections.map((section, index) => (
              <li key={section.section_id}>
                <a
                  href={`#${sectionAnchor(section.section_id)}`}
                  className="flex gap-2.5 rounded px-1 py-0.5 text-muted transition-colors hover:text-gold"
                >
                  <span className="shrink-0 font-mono text-xs leading-5 text-bronze">
                    {String(index + 1).padStart(2, "0")}
                  </span>
                  <span>{section.title}</span>
                </a>
              </li>
            ))}
          </ol>
        </nav>

        <div className="min-w-0 flex-1">
          {sections.map((section, index) => (
            <section
              key={section.section_id}
              id={sectionAnchor(section.section_id)}
              className="mb-14 max-w-reading scroll-mt-8 last:mb-0"
            >
              <p className="mb-2 font-mono text-xs text-bronze">
                {String(index + 1).padStart(2, "0")}
              </p>
              <h2 className="font-serif text-2xl text-ivory sm:text-[1.75rem]">{section.title}</h2>

              {section.summary.trim().length > 0 && (
                <p className="mt-4 border-l-2 border-gold/40 pl-4 text-sm italic leading-relaxed text-muted">
                  {section.summary}
                </p>
              )}

              <div className="report-prose mt-6">
                {splitParagraphs(section.text).map((paragraph, i) => (
                  <p key={i}>{paragraph}</p>
                ))}
              </div>

              <p className="mt-5 text-xs text-muted">{section.word_count.toLocaleString()} words</p>

              <SectionSources section={section} />
            </section>
          ))}
        </div>
      </div>
    </article>
  );
}
