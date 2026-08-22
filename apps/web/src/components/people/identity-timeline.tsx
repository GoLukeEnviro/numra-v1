"use client";

import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { api, type NameIdentityKind, type PersonOut } from "@/api/client";
import { buildIdentityTimeline } from "@/lib/identity";
import { useAsync } from "@/lib/use-async";
import { formatDateTime, formatIsoDate } from "@/lib/utils";

const KIND_LABEL: Record<NameIdentityKind, string> = {
  birth: "Birth",
  current: "Current",
  preferred: "Preferred",
};

/**
 * The real, server-recorded name history (V1.5 Epic C) — every entry Numra has ever
 * written down for this person, append-only. `recorded_at` is always shown (when
 * Numra actually saved the row); `valid_from` is only ever shown when the backend
 * sent one, since it is only ever set from a genuinely known fact (the birth date
 * for the birth identity) — never invented for current/preferred names.
 */
function RecordedHistory({ personId }: { personId: string }) {
  const state = useAsync(() => api.people.identities(personId), [personId]);
  if (state.status !== "success" || state.data.length === 0) return null;

  return (
    <div className="mt-6 border-t border-white/10 pt-5">
      <p className="mb-3 text-xs uppercase tracking-wider text-muted">Recorded history</p>
      <ul className="flex flex-col gap-2.5" aria-label="Recorded history">
        {state.data.map((entry) => {
          const name = [entry.first_names, entry.middle_names, entry.last_name]
            .filter(Boolean)
            .join(" ");
          return (
            <li key={entry.id} className="flex flex-wrap items-baseline gap-x-2 text-sm">
              <Badge variant="neutral">{KIND_LABEL[entry.kind]}</Badge>
              <span className="text-text">{name || "—"}</span>
              <span className="text-xs text-muted">
                {entry.valid_from
                  ? `Valid from ${formatIsoDate(entry.valid_from)}`
                  : `Recorded ${formatDateTime(entry.recorded_at)}`}
              </span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

export function IdentityTimeline({ person }: { person: PersonOut }) {
  const entries = buildIdentityTimeline(person);

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Identity</CardTitle>
        <CardDescription>
          The names recorded for this profile. Only the birth name enters a calculation.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <ol className="relative" aria-label="Current identity">
          {entries.map((entry, index) => {
            const isLast = index === entries.length - 1;
            return (
              <li key={entry.id} className="relative flex gap-4 pb-6 last:pb-0">
                {/* Connector: drawn between markers, never past the final one. */}
                {!isLast && (
                  <span
                    aria-hidden="true"
                    className="absolute left-[5px] top-4 h-[calc(100%-0.5rem)] w-px bg-white/12"
                  />
                )}
                <span
                  aria-hidden="true"
                  className={
                    entry.drivesCoreNumbers
                      ? "relative mt-1.5 h-2.5 w-2.5 shrink-0 rounded-full bg-gold shadow-gold"
                      : "relative mt-1.5 h-2.5 w-2.5 shrink-0 rounded-full border border-muted/70 bg-surface"
                  }
                />
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
                    <p className="text-xs uppercase tracking-wider text-muted">{entry.label}</p>
                    {entry.drivesCoreNumbers && (
                      <Badge variant="success">Used for Core Numbers</Badge>
                    )}
                    {entry.partial && <Badge variant="neutral">Partially recorded</Badge>}
                  </div>
                  <p className="mt-1 font-serif text-xl text-ivory">{entry.name}</p>
                  <p className="mt-1 text-xs leading-relaxed text-muted">{entry.note}</p>
                  {entry.partial && (
                    <p className="mt-1 text-xs leading-relaxed text-muted">
                      Only the name parts stored for this profile are shown — the missing
                      parts are not filled in from the birth name.
                    </p>
                  )}
                </div>
              </li>
            );
          })}
        </ol>

        {entries.length === 1 && (
          <p className="mt-2 border-t border-white/10 pt-4 text-xs leading-relaxed text-muted">
            No current or preferred name is recorded for this profile. Numra shows only the
            names it holds — it does not infer a name history.
          </p>
        )}

        <RecordedHistory personId={person.id} />
      </CardContent>
    </Card>
  );
}
