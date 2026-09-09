import { describe, expect, it } from "vitest";
import type { ConsentGrantOut, WorkspaceConsentOut } from "@/api/client";
import { summarizeConsent } from "@/lib/workspace-consent";

function grant(overrides: Partial<ConsentGrantOut> = {}): ConsentGrantOut {
  return {
    id: "g1",
    workspace_id: "ws-1",
    grantor_user_id: "u1",
    grantee_user_id: "u2",
    scope: "CORE_NUMEROLOGY",
    granted_at: "2026-01-01T00:00:00Z",
    revoked_at: null,
    version: 1,
    ...overrides,
  } as ConsentGrantOut;
}

function consent(overrides: Partial<WorkspaceConsentOut> = {}): WorkspaceConsentOut {
  return { granted_by_me: [], granted_to_me: [], ...overrides };
}

describe("summarizeConsent", () => {
  it("counts active granted-by-me and granted-to-me scopes separately", () => {
    const summary = summarizeConsent(
      consent({
        granted_by_me: [grant({ scope: "CORE_NUMEROLOGY" }), grant({ scope: "CURRENT_TIMING" })],
        granted_to_me: [grant({ scope: "RELATIONSHIP_INSIGHTS" })],
      }),
    );
    expect(summary.grantedByMeCount).toBe(2);
    expect(summary.grantedToMeCount).toBe(1);
    expect(summary.totalScopes).toBe(8);
  });

  it("ignores revoked grants", () => {
    const summary = summarizeConsent(
      consent({
        granted_by_me: [
          grant({ scope: "CORE_NUMEROLOGY", revoked_at: "2026-02-01T00:00:00Z" }),
          grant({ scope: "CURRENT_TIMING" }),
        ],
      }),
    );
    expect(summary.grantedByMeCount).toBe(1);
  });

  it("deduplicates repeated grants for the same scope", () => {
    const summary = summarizeConsent(
      consent({
        granted_by_me: [grant({ scope: "CORE_NUMEROLOGY" }), grant({ scope: "CORE_NUMEROLOGY", id: "g2" })],
      }),
    );
    expect(summary.grantedByMeCount).toBe(1);
  });

  it("returns zero counts for empty consent", () => {
    const summary = summarizeConsent(consent());
    expect(summary.grantedByMeCount).toBe(0);
    expect(summary.grantedToMeCount).toBe(0);
  });
});
