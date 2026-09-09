import type { PersonOut } from "@/api/client";
import type { WorkspaceOption } from "@/components/workspaces/workspace-switcher";
import { personDisplayName } from "@/lib/identity";

/**
 * Adapts the account's people (api.people.list()) into WorkspaceOption[] for the
 * Personal Workspace hub's switcher -- every entry is `kind: "PERSONAL"`
 * (relationship workspaces are a separate, unrelated switcher use, out of scope
 * here, see api/client.ts's V2 namespace block comment). The label carries the
 * SELF/managed profile-type suffix so it stays visible in the switcher dropdown
 * (specs/v2/minor-profile-policy.md's `person_account_mode`).
 */
export function peopleToWorkspaceOptions(
  people: PersonOut[],
  profileTypeSuffix: (person: PersonOut) => string,
): WorkspaceOption[] {
  return people.map((person) => ({
    id: person.id,
    label: `${personDisplayName(person)} (${profileTypeSuffix(person)})`,
    kind: "PERSONAL",
  }));
}
