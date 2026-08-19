/**
 * Client-side cache of relationships this browser has created, mirroring
 * local-calculations.ts. `openapi/numra-v1.json` has no "list relationships"
 * endpoint, only `POST /v1/relationships` and `GET /v1/relationships/{id}` — so
 * a "recent comparisons" list on /relationships is only possible by
 * remembering ids the app itself created. Purely a navigation convenience.
 */

const STORAGE_KEY = "numra:relationships:v1";

export interface CachedRelationship {
  relationshipId: string;
  labelA: string;
  labelB: string;
  savedAt: string;
}

function readAll(): CachedRelationship[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed: unknown = JSON.parse(raw);
    return Array.isArray(parsed) ? (parsed as CachedRelationship[]) : [];
  } catch {
    return [];
  }
}

function writeAll(entries: CachedRelationship[]): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(entries));
  } catch {
    // Convenience cache only — ignore storage failures.
  }
}

export function recordRelationship(entry: Omit<CachedRelationship, "savedAt">): void {
  const entries = readAll().filter((e) => e.relationshipId !== entry.relationshipId);
  entries.unshift({ ...entry, savedAt: new Date().toISOString() });
  writeAll(entries.slice(0, 50));
}

export function getAllCachedRelationships(): CachedRelationship[] {
  return readAll();
}
