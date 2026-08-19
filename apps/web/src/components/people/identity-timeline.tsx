import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import type { PersonOut } from "@/api/client";
import { buildIdentityTimeline } from "@/lib/identity";

/**
 * Identity Timeline: the names Numra actually holds for a person, and which of them
 * a calculation uses.
 *
 * Explicitly *not* a name history. The backend has no endpoint that records when a
 * name changed and nothing writes to its `name_identities` table, so no dates, no
 * previous names and no ordering beyond birth → current → preferred are shown. Each
 * row exists only because `GET /v1/people/{id}` returned a value for it.
 */
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
        <ol className="relative">
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
      </CardContent>
    </Card>
  );
}
