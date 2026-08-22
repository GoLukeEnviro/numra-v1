import type { PersonOut } from "@/api/client";

/**
 * Builds the "Identity" snapshot shown on a person's profile — birth/current/
 * preferred, derived only from fields `GET /v1/people/{id}` returns right now (no
 * dates, no past names inferred).
 *
 * The real, server-recorded name *history* (V1.5 Epic C — `GET
 * /v1/people/{id}/identities`, append-only, `recorded_at`/`valid_from` kept
 * strictly separate so no date is ever invented) is rendered separately by
 * `RecordedHistory` in `identity-timeline.tsx`, underneath this snapshot.
 *
 * canon-spec.md §5 is the source for the "what this name is used for" copy: the Core
 * is computed from the **full birth name** only. Current and preferred names are
 * stored metadata in this version and never influence a Core Number.
 */

export type IdentityEntryId = "birth" | "current" | "preferred";

export interface IdentityEntry {
  id: IdentityEntryId;
  label: string;
  name: string;
  /** What this name is (and is not) used for. Never a numerological claim. */
  note: string;
  /** True for the name the Core Numbers are actually computed from. */
  drivesCoreNumbers: boolean;
  /**
   * True when only *some* of the first/middle/last fields are recorded for this
   * name, so the UI can say the entry is partial instead of implying it is the
   * person's complete legal name.
   */
  partial: boolean;
}

function joinName(parts: (string | null | undefined)[]): string {
  return parts
    .map((part) => part?.trim() ?? "")
    .filter((part) => part.length > 0)
    .join(" ");
}

/** Case- and whitespace-insensitive comparison, for "is this actually different?". */
function sameName(a: string, b: string): boolean {
  const normalize = (s: string) => s.trim().replace(/\s+/g, " ").toLocaleLowerCase();
  return normalize(a) === normalize(b);
}

export function buildIdentityTimeline(person: PersonOut): IdentityEntry[] {
  const entries: IdentityEntry[] = [];

  const birthName = joinName([
    person.birth_first_names,
    person.birth_middle_names,
    person.birth_last_name,
  ]);

  // Always present: birth_first_names and birth_last_name are required by the API.
  entries.push({
    id: "birth",
    label: "Birth name",
    name: birthName,
    note: "Every Core Number is computed from this name (canon-spec §5).",
    drivesCoreNumbers: true,
    partial: false,
  });

  const currentName = joinName([
    person.current_first_names,
    person.current_middle_names,
    person.current_last_name,
  ]);
  // Shown only when a current name is recorded *and* it is not simply a restatement
  // of the birth name — an identical entry would suggest a change that never happened.
  if (currentName.length > 0 && !sameName(currentName, birthName)) {
    const hasFirst = (person.current_first_names ?? "").trim().length > 0;
    const hasLast = (person.current_last_name ?? "").trim().length > 0;
    entries.push({
      id: "current",
      label: "Current name",
      name: currentName,
      note: "Recorded as metadata — it does not change any Core Number in this version.",
      drivesCoreNumbers: false,
      partial: !(hasFirst && hasLast),
    });
  }

  const preferredName = (person.preferred_name ?? "").trim();
  if (preferredName.length > 0) {
    entries.push({
      id: "preferred",
      label: "Preferred name",
      name: preferredName,
      note: "How this person is addressed in Numra. Never used in a calculation.",
      drivesCoreNumbers: false,
      partial: false,
    });
  }

  return entries;
}

/** The label to show for a person across the app: preferred name if set, else birth name. */
export function personDisplayName(person: PersonOut): string {
  const preferred = person.preferred_name?.trim();
  if (preferred) return preferred;
  return joinName([person.birth_first_names, person.birth_last_name]);
}
