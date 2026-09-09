import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import WorkspacesPage from "@/app/workspaces/page";
import { LocaleProvider } from "@/i18n/context";
import { useAuth } from "@/lib/auth-context";
import { api, type UserConnectionOut, type WorkspaceSummaryOut } from "@/api/client";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  usePathname: () => "/workspaces",
}));

vi.mock("@/lib/auth-context", () => ({ useAuth: vi.fn() }));

vi.mock("@/api/client", async () => {
  const actual = await vi.importActual<typeof import("@/api/client")>("@/api/client");
  return {
    ...actual,
    api: {
      workspaces: { list: vi.fn() },
      connections: { list: vi.fn() },
    },
  };
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

function renderPage() {
  return render(
    <LocaleProvider>
      <WorkspacesPage />
    </LocaleProvider>,
  );
}

beforeEach(() => {
  vi.mocked(useAuth).mockReturnValue({
    status: "authenticated",
    user: { id: "user-1", email: "me@example.com", role: "USER", is_active: true },
    error: null,
    login: vi.fn(),
    register: vi.fn(),
    logout: vi.fn(),
    refresh: vi.fn(),
  } as ReturnType<typeof useAuth>);
  vi.mocked(api.workspaces.list).mockReset();
  vi.mocked(api.connections.list).mockReset();
});

describe("WorkspacesPage", () => {
  it("shows the empty state with a link to connections when no workspaces exist", async () => {
    vi.mocked(api.workspaces.list).mockResolvedValue([]);
    vi.mocked(api.connections.list).mockResolvedValue([]);
    renderPage();

    expect(await screen.findByText("Noch keine Workspaces")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Verbindungen ansehen" })).toHaveAttribute("href", "/connections");
  });

  it("renders active workspaces joined to the counterpart name, and separates dissolved ones", async () => {
    vi.mocked(api.workspaces.list).mockResolvedValue([
      workspace({ id: "ws-1", connection_id: "conn-1", status: "ACTIVE" }),
      workspace({
        id: "ws-2",
        connection_id: "conn-2",
        status: "DISSOLVED",
        dissolved_at: "2026-03-01T00:00:00Z",
      }),
    ]);
    vi.mocked(api.connections.list).mockResolvedValue([
      connection({ id: "conn-1", counterpart_display_name: "Ada Lovelace" }),
      connection({ id: "conn-2", counterpart_user_id: "user-3", counterpart_display_name: "Grace Hopper" }),
    ]);
    renderPage();

    expect(await screen.findByText("Aktive Workspaces")).toBeInTheDocument();
    expect(screen.getByText("Aufgelöste Workspaces")).toBeInTheDocument();
    expect(screen.getByText("Ada Lovelace")).toBeInTheDocument();
    expect(screen.getByText("Grace Hopper")).toBeInTheDocument();
  });

  it("does not render the dissolved section when there are no dissolved workspaces", async () => {
    vi.mocked(api.workspaces.list).mockResolvedValue([workspace()]);
    vi.mocked(api.connections.list).mockResolvedValue([connection()]);
    renderPage();

    await screen.findByText("Ada Lovelace");
    expect(screen.queryByText("Aufgelöste Workspaces")).not.toBeInTheDocument();
  });

  it("shows a neutral fallback name when the connection join finds no match", async () => {
    vi.mocked(api.workspaces.list).mockResolvedValue([workspace({ connection_id: "conn-missing" })]);
    vi.mocked(api.connections.list).mockResolvedValue([]);
    renderPage();

    expect(await screen.findByText("Unbekannte Verbindung")).toBeInTheDocument();
  });

  it("shows an unset-type hint for a workspace without a relationship type", async () => {
    vi.mocked(api.workspaces.list).mockResolvedValue([workspace({ relationship_type: null })]);
    vi.mocked(api.connections.list).mockResolvedValue([connection()]);
    renderPage();

    expect(await screen.findByText("Typ nicht gesetzt")).toBeInTheDocument();
  });
});
