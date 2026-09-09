import type { WorkspaceSummaryOut } from "@/api/client";
import type { WorkspaceOption } from "@/components/workspaces/workspace-switcher";
import { buildCounterpartNameMap } from "@/lib/identity";

/**
 * Adapts a Relationship Workspace list into `WorkspaceOption[]` for the hub's
 * switcher -- every entry is `kind: "RELATIONSHIP"` (the counterpart to
 * `workspace-switcher-personal.ts`'s `peopleToWorkspaceOptions`). Reuses
 * `buildCounterpartNameMap` (the same join the workspace list uses) rather than
 * re-deriving the counterpart name here.
 */
export function workspacesToWorkspaceOptions(
  workspaces: WorkspaceSummaryOut[],
  counterpartNameById: ReturnType<typeof buildCounterpartNameMap>,
  fallbackLabel: string,
): WorkspaceOption[] {
  return workspaces.map((w) => ({
    id: w.id,
    label: counterpartNameById.get(w.id) ?? fallbackLabel,
    kind: "RELATIONSHIP" as const,
  }));
}
