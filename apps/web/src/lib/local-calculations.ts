/**
 * Client-side cache mapping a person to the calculations run for them.
 *
 * Judgment call: `openapi/numra-v1.json` has no `GET /v1/people/{id}/calculations`
 * (list) endpoint and `PersonOut` carries no "latest calculation" reference — a
 * calculation's id is only ever learned by creating one (`POST
 * .../calculations`) or by already having it (e.g. from a URL). So the app
 * remembers calculation ids it has seen, per person, in localStorage. This is
 * purely a navigation convenience (dashboard links, relationship picker) — it
 * never stands in for backend data and is never treated as authoritative; the
 * calculation itself is always re-fetched from the API when opened.
 */

const STORAGE_KEY = "numra:calculations:v1";

export interface CachedCalculation {
  calculationId: string;
  personId: string;
  personLabel: string;
  asOfDate: string;
  savedAt: string;
}

function readAll(): CachedCalculation[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed: unknown = JSON.parse(raw);
    return Array.isArray(parsed) ? (parsed as CachedCalculation[]) : [];
  } catch {
    return [];
  }
}

function writeAll(entries: CachedCalculation[]): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(entries));
  } catch {
    // Storage unavailable (private browsing, quota) — degrade silently, this
    // cache is a convenience layer only.
  }
}

export function recordCalculation(entry: Omit<CachedCalculation, "savedAt">): void {
  const entries = readAll().filter((e) => e.calculationId !== entry.calculationId);
  entries.unshift({ ...entry, savedAt: new Date().toISOString() });
  writeAll(entries.slice(0, 100));
}

export function getLatestForPerson(personId: string): CachedCalculation | undefined {
  return readAll().find((e) => e.personId === personId);
}

export function getAllCached(): CachedCalculation[] {
  return readAll();
}
