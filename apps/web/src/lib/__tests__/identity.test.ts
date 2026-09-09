import { describe, expect, it } from "vitest";
import type { PersonOut, UserConnectionOut, WorkspaceSummaryOut } from "@/api/client";
import { buildCounterpartNameMap, buildIdentityTimeline, personDisplayName } from "@/lib/identity";

function person(overrides: Partial<PersonOut> = {}): PersonOut {
  return {
    id: "p1",
    birth_first_names: "Lukas",
    birth_middle_names: null,
    birth_last_name: "Springer",
    birth_date: "1986-07-18",
    birth_time: null,
    birth_place: null,
    current_first_names: null,
    current_middle_names: null,
    current_last_name: null,
    preferred_name: null,
    created_at: "2026-08-19T09:00:00Z",
    updated_at: "2026-08-19T09:00:00Z",
    ...overrides,
  } as PersonOut;
}

describe("buildIdentityTimeline", () => {
  it("always shows the birth name, and marks it as the one driving Core Numbers", () => {
    const entries = buildIdentityTimeline(person());
    expect(entries).toHaveLength(1);
    expect(entries[0]?.id).toBe("birth");
    expect(entries[0]?.name).toBe("Lukas Springer");
    expect(entries[0]?.drivesCoreNumbers).toBe(true);
  });

  it("includes middle names in the birth name, in canon-spec order", () => {
    const entries = buildIdentityTimeline(person({ birth_middle_names: "Maria Josef" }));
    expect(entries[0]?.name).toBe("Lukas Maria Josef Springer");
  });

  it("omits the current name when the API returned none", () => {
    const entries = buildIdentityTimeline(person());
    expect(entries.some((e) => e.id === "current")).toBe(false);
  });

  it("omits the current name when it merely restates the birth name", () => {
    // Showing it would imply a name change that never happened.
    const entries = buildIdentityTimeline(
      person({ current_first_names: "lukas", current_last_name: "SPRINGER" }),
    );
    expect(entries.some((e) => e.id === "current")).toBe(false);
  });

  it("shows a genuinely different current name, and never as a Core Number source", () => {
    const entries = buildIdentityTimeline(
      person({ current_first_names: "Lukas", current_last_name: "Springer-Meier" }),
    );
    const current = entries.find((e) => e.id === "current");
    expect(current?.name).toBe("Lukas Springer-Meier");
    expect(current?.drivesCoreNumbers).toBe(false);
    expect(current?.partial).toBe(false);
  });

  it("flags a current name as partial rather than completing it from the birth name", () => {
    const entries = buildIdentityTimeline(person({ current_last_name: "Meier" }));
    const current = entries.find((e) => e.id === "current");
    expect(current?.name).toBe("Meier");
    expect(current?.partial).toBe(true);
  });

  it("shows a preferred name only when one is recorded", () => {
    expect(buildIdentityTimeline(person()).some((e) => e.id === "preferred")).toBe(false);
    const entries = buildIdentityTimeline(person({ preferred_name: "Luke" }));
    expect(entries.find((e) => e.id === "preferred")?.name).toBe("Luke");
  });

  it("treats whitespace-only optional names as absent", () => {
    const entries = buildIdentityTimeline(
      person({ preferred_name: "   ", current_last_name: "  " }),
    );
    expect(entries).toHaveLength(1);
  });

  it("orders entries birth → current → preferred", () => {
    const entries = buildIdentityTimeline(
      person({
        current_first_names: "Luca",
        current_last_name: "Meier",
        preferred_name: "Luke",
      }),
    );
    expect(entries.map((e) => e.id)).toEqual(["birth", "current", "preferred"]);
  });
});

describe("personDisplayName", () => {
  it("prefers the preferred name when set", () => {
    expect(personDisplayName(person({ preferred_name: "Luke" }))).toBe("Luke");
  });

  it("falls back to first and last birth name", () => {
    expect(personDisplayName(person())).toBe("Lukas Springer");
  });
});

function connection(overrides: Partial<UserConnectionOut> = {}): UserConnectionOut {
  return {
    id: "conn-1",
    counterpart_user_id: "user-2",
    counterpart_display_name: "Ada Lovelace",
    status: "ACTIVE",
    created_at: "2026-01-01T00:00:00Z",
    dissolved_at: null,
    ...overrides,
  } as UserConnectionOut;
}

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

describe("buildCounterpartNameMap", () => {
  it("joins a workspace to its counterpart's name via connection_id", () => {
    const map = buildCounterpartNameMap([connection()], [workspace()]);
    expect(map.get("ws-1")).toBe("Ada Lovelace");
  });

  it("omits a workspace whose connection has no matching entry", () => {
    const map = buildCounterpartNameMap([], [workspace({ id: "ws-2", connection_id: "conn-missing" })]);
    expect(map.has("ws-2")).toBe(false);
  });

  it("joins multiple workspaces independently", () => {
    const map = buildCounterpartNameMap(
      [connection(), connection({ id: "conn-2", counterpart_display_name: "Grace Hopper" })],
      [workspace(), workspace({ id: "ws-2", connection_id: "conn-2" })],
    );
    expect(map.get("ws-1")).toBe("Ada Lovelace");
    expect(map.get("ws-2")).toBe("Grace Hopper");
  });
});
