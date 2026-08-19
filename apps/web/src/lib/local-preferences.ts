/**
 * Tiny localStorage-backed UI preferences. Navigation convenience only — nothing
 * here is ever rendered as data, and every value is re-validated against the API
 * before use (a remembered person id that no longer exists simply falls back to the
 * picker).
 */

const TODAY_PERSON_KEY = "numra:today:person:v1";

function read(key: string): string | null {
  if (typeof window === "undefined") return null;
  try {
    return window.localStorage.getItem(key);
  } catch {
    return null;
  }
}

function write(key: string, value: string): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(key, value);
  } catch {
    // Storage unavailable (private browsing, quota) — degrade silently.
  }
}

/** The person the Today page was last opened for, so the page opens straight into it. */
export function getTodayPersonId(): string | null {
  return read(TODAY_PERSON_KEY);
}

export function setTodayPersonId(personId: string): void {
  write(TODAY_PERSON_KEY, personId);
}
