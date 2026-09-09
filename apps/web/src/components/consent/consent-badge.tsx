import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";

export type ConsentStatus = "GRANTED" | "REVOKED" | "PENDING";

export interface ConsentBadgeProps {
  status: ConsentStatus;
  label?: string;
}

// REVOKED is a normal, expected state (the grantor withdrew a scope they previously
// allowed) -- never rendered in the alarming red the diagnostic variant would imply
// elsewhere, only a deliberately muted, "not equal weight to a canonical value" tag.
const STATUS_VARIANT = {
  GRANTED: "success",
  PENDING: "neutral",
  REVOKED: "diagnostic",
} as const;

export function ConsentBadge({ status, label }: ConsentBadgeProps) {
  return <Badge variant={STATUS_VARIANT[status]}>{label ?? status}</Badge>;
}

export interface ConsentListEntry {
  id: string;
  participantName: string;
  status: ConsentStatus;
}

export interface ConsentListProps {
  entries: ConsentListEntry[];
  emptyLabel?: string;
}

// Pure presentation: no fetch, no hook -- the caller supplies `entries` (PR-WEB-00
// scope boundary, see api/client.ts's V2 namespace block comment).
export function ConsentList({ entries, emptyLabel = "No consent entries yet." }: ConsentListProps) {
  return (
    <Card>
      <CardContent>
        {entries.length === 0 ? (
          <p className="text-sm text-muted">{emptyLabel}</p>
        ) : (
          <ul className="flex flex-col gap-2">
            {entries.map((entry) => (
              <li key={entry.id} className="flex items-center justify-between gap-3 text-sm">
                <span className="text-text">{entry.participantName}</span>
                <ConsentBadge status={entry.status} />
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
