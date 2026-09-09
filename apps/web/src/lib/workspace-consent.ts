import type { WorkspaceConsentOut } from "@/api/client";

/** Fixed per canon-spec/consent-spec: 8 `ConsentScope` values total (3 default + 5
 *  extended, see `app/workspaces/[id]/consent/page.tsx`'s DEFAULT_SCOPES/
 *  EXTENDED_SCOPES). Not derived from the response -- the response only ever lists
 *  scopes that were actually granted, never the full catalog. */
const TOTAL_CONSENT_SCOPES = 8;

export interface ConsentSummary {
  grantedByMeCount: number;
  grantedToMeCount: number;
  totalScopes: number;
}

/** Pure aggregation over a `WorkspaceConsentOut` for the hub's summary card --
 *  counts distinct, currently-active (non-revoked) scopes on each side. A scope
 *  could in principle appear more than once across grant history, so the count is
 *  deduplicated by scope, not by grant record. */
export function summarizeConsent(consent: WorkspaceConsentOut): ConsentSummary {
  const activeByMe = consent.granted_by_me.filter((g) => g.revoked_at === null);
  const activeToMe = consent.granted_to_me.filter((g) => g.revoked_at === null);
  return {
    grantedByMeCount: new Set(activeByMe.map((g) => g.scope)).size,
    grantedToMeCount: new Set(activeToMe.map((g) => g.scope)).size,
    totalScopes: TOTAL_CONSENT_SCOPES,
  };
}
