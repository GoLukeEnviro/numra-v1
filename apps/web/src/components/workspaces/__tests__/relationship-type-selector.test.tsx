import { act, fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { RelationshipTypeSelector } from "@/components/workspaces/relationship-type-selector";
import { LocaleProvider } from "@/i18n/context";
import { ApiError, api, type WorkspaceOut } from "@/api/client";

vi.mock("@/api/client", async () => {
  const actual = await vi.importActual<typeof import("@/api/client")>("@/api/client");
  return { ...actual, api: { workspaces: { patch: vi.fn() } } };
});

function workspace(overrides: Partial<WorkspaceOut> = {}): WorkspaceOut {
  return {
    id: "ws-1",
    connection_id: "conn-1",
    status: "ACTIVE",
    relationship_type: null,
    created_at: "2026-01-01T00:00:00Z",
    dissolved_at: null,
    ...overrides,
  } as WorkspaceOut;
}

function renderSelector(ws: WorkspaceOut) {
  return render(
    <LocaleProvider>
      <RelationshipTypeSelector workspaceId="ws-1" workspace={ws} />
    </LocaleProvider>,
  );
}

beforeEach(() => {
  vi.mocked(api.workspaces.patch).mockReset();
});

describe("RelationshipTypeSelector", () => {
  it("shows the placeholder option when no type is set, without a silent preselection", () => {
    renderSelector(workspace());
    expect(screen.getByRole("combobox")).toHaveValue("");
    expect(screen.getByText("Nicht gesetzt")).toBeInTheDocument();
  });

  it("saves the selected type via PATCH and shows inline success feedback", async () => {
    vi.mocked(api.workspaces.patch).mockResolvedValue(workspace({ relationship_type: "PARTNER" }));
    renderSelector(workspace());

    fireEvent.change(screen.getByRole("combobox"), { target: { value: "PARTNER" } });
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Speichern" }));
    });

    expect(api.workspaces.patch).toHaveBeenCalledWith("ws-1", { relationship_type: "PARTNER" });
    expect(await screen.findByText("Gespeichert")).toBeInTheDocument();
  });

  it("shows an inline error and keeps the previous state when the PATCH fails", async () => {
    vi.mocked(api.workspaces.patch).mockRejectedValue(new Error("network"));
    renderSelector(workspace());

    fireEvent.change(screen.getByRole("combobox"), { target: { value: "FRIENDSHIP" } });
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Speichern" }));
    });

    expect(await screen.findByText("Speichern fehlgeschlagen — bitte erneut versuchen")).toBeInTheDocument();
  });

  it("renders a read-only PhaseDisabledState with no interactive control when the workspace is DISSOLVED", () => {
    renderSelector(workspace({ status: "DISSOLVED", relationship_type: "PARTNER" }));

    expect(screen.getByText("Workspace aufgelöst")).toBeInTheDocument();
    expect(screen.queryByRole("combobox")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Speichern" })).not.toBeInTheDocument();
    expect(screen.getByText((_, node) => node?.textContent === "Zuletzt gesetzt: Partner")).toBeInTheDocument();
  });

  it("degrades to the read-only DISSOLVED state when the PATCH itself races into WORKSPACE_DISSOLVED", async () => {
    vi.mocked(api.workspaces.patch).mockRejectedValue(
      new ApiError("dissolved", "WORKSPACE_DISSOLVED", 409),
    );
    renderSelector(workspace());

    fireEvent.change(screen.getByRole("combobox"), { target: { value: "PARTNER" } });
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Speichern" }));
    });

    expect(await screen.findByText("Workspace aufgelöst")).toBeInTheDocument();
    expect(screen.queryByText("Speichern fehlgeschlagen — bitte erneut versuchen")).not.toBeInTheDocument();
  });
});
