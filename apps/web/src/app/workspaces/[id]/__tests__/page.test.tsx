import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import RelationshipWorkspaceHubPage from "@/app/workspaces/[id]/page";
import { LocaleProvider } from "@/i18n/context";
import { useAuth } from "@/lib/auth-context";
import { api, type WorkspaceOverviewOut } from "@/api/client";

const useParams = vi.fn();
vi.mock("next/navigation", () => ({
  useParams: () => useParams(),
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  usePathname: () => "/workspaces/ws-1",
}));

vi.mock("@/lib/auth-context", () => ({ useAuth: vi.fn() }));

vi.mock("@/api/client", async () => {
  const actual = await vi.importActual<typeof import("@/api/client")>("@/api/client");
  return {
    ...actual,
    api: {
      workspaces: {
        get: vi.fn(),
        list: vi.fn(),
        patch: vi.fn(),
        consent: { list: vi.fn() },
      },
      connections: { list: vi.fn() },
    },
  };
});

function overview(overrides: Partial<WorkspaceOverviewOut> = {}): WorkspaceOverviewOut {
  return {
    workspace: {
      id: "ws-1",
      connection_id: "conn-1",
      status: "ACTIVE",
      relationship_type: null,
      created_at: "2026-01-01T00:00:00Z",
      dissolved_at: null,
    },
    dual_profile: [
      { user_id: "me", display_name: "Lukas Springer", self_person: { id: "p1", display_name: "Lukas Springer" }, core_numbers: { life_path: { display_value: "8" } } },
      { user_id: "them", display_name: "Ada Lovelace", self_person: null, core_numbers: null },
    ],
    ...overrides,
  } as WorkspaceOverviewOut;
}

function renderPage() {
  return render(
    <LocaleProvider>
      <RelationshipWorkspaceHubPage />
    </LocaleProvider>,
  );
}

beforeEach(() => {
  useParams.mockReturnValue({ id: "ws-1" });
  vi.mocked(useAuth).mockReturnValue({
    status: "authenticated",
    user: { id: "me", email: "me@example.com", role: "USER", is_active: true },
    error: null,
    login: vi.fn(),
    register: vi.fn(),
    logout: vi.fn(),
    refresh: vi.fn(),
  } as ReturnType<typeof useAuth>);
  vi.mocked(api.workspaces.get).mockReset();
  vi.mocked(api.workspaces.list).mockReset().mockResolvedValue([]);
  vi.mocked(api.workspaces.consent.list).mockReset().mockResolvedValue({ granted_by_me: [], granted_to_me: [] });
  vi.mocked(api.connections.list).mockReset().mockResolvedValue([]);
});

describe("RelationshipWorkspaceHubPage", () => {
  it("shows the counterpart name as the header title once loaded", async () => {
    vi.mocked(api.workspaces.get).mockResolvedValue(overview());
    renderPage();

    expect(await screen.findByRole("heading", { name: "Ada Lovelace", level: 1 })).toBeInTheDocument();
  });

  it("renders all six feature stub cards", async () => {
    vi.mocked(api.workspaces.get).mockResolvedValue(overview());
    renderPage();

    await screen.findByRole("heading", { name: "Ada Lovelace", level: 1 });
    for (const title of ["Dynamics", "Check-ins", "Aufgaben", "Roadmap", "Geteilte Reflexion", "Copilot"]) {
      expect(screen.getAllByText(title).length).toBeGreaterThan(0);
    }
  });

  it("keeps showing Loading instead of stale data while the workspace id in the response does not yet match the route (state isolation)", async () => {
    // Resolve is deliberately deferred until after the render assertion below, so the
    // first render commits while the async call is still in flight and the guard's
    // "workspace.id === workspaceId" branch has nothing to compare yet.
    let resolveGet: (value: WorkspaceOverviewOut) => void = () => {};
    vi.mocked(api.workspaces.get).mockImplementation(
      () => new Promise((resolve) => (resolveGet = resolve)),
    );
    renderPage();

    expect(screen.getByText("Workspace wird geladen…")).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Ada Lovelace", level: 1 })).not.toBeInTheDocument();

    resolveGet(overview());
    expect(await screen.findByRole("heading", { name: "Ada Lovelace", level: 1 })).toBeInTheDocument();
  });

  it("shows Loading (never stale data) when a stale response for a previous workspace id resolves after navigating", async () => {
    vi.mocked(api.workspaces.get).mockResolvedValue(overview({
      workspace: {
        id: "ws-OLD",
        connection_id: "conn-1",
        status: "ACTIVE",
        relationship_type: null,
        created_at: "2026-01-01T00:00:00Z",
        dissolved_at: null,
      },
    }));
    renderPage();

    await screen.findByText("Workspace wird geladen…");
    expect(screen.queryByRole("heading", { name: "Ada Lovelace", level: 1 })).not.toBeInTheDocument();
  });
});
