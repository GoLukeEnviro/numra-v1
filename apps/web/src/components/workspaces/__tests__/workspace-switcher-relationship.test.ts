import { describe, expect, it } from "vitest";
import type { WorkspaceSummaryOut } from "@/api/client";
import { workspacesToWorkspaceOptions } from "@/components/workspaces/workspace-switcher-relationship";

function workspace(overrides: Partial<WorkspaceSummaryOut> = {}): WorkspaceSummaryOut {
  return {
    id: "ws-1",
    connection_id: "conn-1",
    status: "ACTIVE",
    relationship_type: null,
    created_at: "2026-01-01T00:00:00Z",
    dissolved_at: null,
    ...overrides,
  } as WorkspaceSummaryOut;
}

describe("workspacesToWorkspaceOptions", () => {
  it("maps each workspace to a RELATIONSHIP option using the joined counterpart name", () => {
    const options = workspacesToWorkspaceOptions(
      [workspace()],
      new Map([["ws-1", "Ada Lovelace"]]),
      "Unbekannt",
    );
    expect(options).toEqual([{ id: "ws-1", label: "Ada Lovelace", kind: "RELATIONSHIP" }]);
  });

  it("falls back to the provided label when the workspace has no joined name", () => {
    const options = workspacesToWorkspaceOptions([workspace({ id: "ws-2" })], new Map(), "Unbekannt");
    expect(options[0]).toEqual({ id: "ws-2", label: "Unbekannt", kind: "RELATIONSHIP" });
  });
});
