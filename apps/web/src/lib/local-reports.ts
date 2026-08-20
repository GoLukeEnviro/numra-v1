/**
 * Client-side cache of reports this browser has started, per calculation.
 *
 * Same judgment call as local-calculations.ts / local-relationships.ts: the API has
 * `POST /v1/reports` and `GET /v1/reports/{id}` but no "list reports" endpoint, so a
 * report id is only ever learned at the moment it is created. Remembering those ids
 * locally is what makes "reports for this calculation" navigable at all.
 *
 * Purely a navigation convenience. Nothing cached here is ever rendered as report
 * content or as a status — the report itself is always re-fetched from the API when
 * opened, and the API's status is the only one shown.
 */

const STORAGE_KEY = "numra:reports:v1";

export interface CachedReport {
  reportId: string;
  jobId: string;
  calculationId: string;
  reportType: string;
  personLabel: string;
  savedAt: string;
}

function readAll(): CachedReport[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed: unknown = JSON.parse(raw);
    return Array.isArray(parsed) ? (parsed as CachedReport[]) : [];
  } catch {
    return [];
  }
}

function writeAll(entries: CachedReport[]): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(entries));
  } catch {
    // Convenience cache only — ignore storage failures (private mode, quota).
  }
}

export function recordReport(entry: Omit<CachedReport, "savedAt">): void {
  const entries = readAll().filter((e) => e.reportId !== entry.reportId);
  entries.unshift({ ...entry, savedAt: new Date().toISOString() });
  writeAll(entries.slice(0, 100));
}

export function getReportsForCalculation(calculationId: string): CachedReport[] {
  return readAll().filter((e) => e.calculationId === calculationId);
}

export function getAllCachedReports(): CachedReport[] {
  return readAll();
}
