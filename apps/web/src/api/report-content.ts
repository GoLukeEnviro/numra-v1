/**
 * Frontend-side type model for `ReportOut.content`.
 *
 * The generated OpenAPI schema types `content` as `{ [key: string]: unknown } | null`
 * because the backend stores the assembled report as an open JSON column. The real
 * shape is pinned by `StructuredReport` / `StructuredReportSection` in
 * packages/engine-interpretation/src/numra_interpretation/report/schemas.py — this
 * module mirrors that contract so the reading page can work with typed data.
 *
 * Like api/canonical-profile.ts this is a type + shallow structural guard, never a
 * re-implementation: nothing here derives, reformats or infers a numeric value. A
 * payload that does not match produces an error state rather than a partial render.
 */

export interface StructuredReportSection {
  section_id: string;
  title: string;
  order_index: number;
  text: string;
  word_count: number;
  summary: string;
  /** V1.5 Epic M — provenance: which profile metrics / knowledge entries this
   *  section was grounded in. Absent on reports generated before this field
   *  existed, so always optional. */
  metric_refs?: string[];
  knowledge_refs?: string[];
}

export interface StructuredReport {
  report_type: string;
  language: string;
  calculation_id?: string;
  calculation_version: string;
  knowledge_version: string;
  prompt_version: string;
  model_provider: string;
  model_name: string;
  total_word_count: number;
  sections: StructuredReportSection[];
}

function isSection(value: unknown): value is StructuredReportSection {
  if (typeof value !== "object" || value === null) return false;
  const v = value as Record<string, unknown>;
  return (
    typeof v.section_id === "string" &&
    typeof v.title === "string" &&
    typeof v.order_index === "number" &&
    typeof v.text === "string"
  );
}

export function asStructuredReport(value: unknown): StructuredReport | null {
  if (typeof value !== "object" || value === null) return null;
  const v = value as Record<string, unknown>;
  if (!Array.isArray(v.sections)) return null;
  if (!v.sections.every(isSection)) return null;
  return value as unknown as StructuredReport;
}

/**
 * Sections in explicit `order_index` order. The API already returns them ordered,
 * but the reading page depends on the order being correct for a long-form document,
 * so it is asserted here rather than assumed. Returns a new array — never mutates
 * the payload the API returned.
 */
export function orderedSections(report: StructuredReport): StructuredReportSection[] {
  return [...report.sections].sort((a, b) => a.order_index - b.order_index);
}
