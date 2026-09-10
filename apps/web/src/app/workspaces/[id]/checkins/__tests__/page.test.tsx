import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import WorkspaceCheckinsPage from "@/app/workspaces/[id]/checkins/page";
import { LocaleProvider } from "@/i18n/context";
import { useAuth } from "@/lib/auth-context";
import { api, ApiError, type WorkspaceOverviewOut } from "@/api/client";

vi.mock("next/navigation", () => ({
  useParams: () => ({ id: "ws-1" }),
  usePathname: () => "/workspaces/ws-1/checkins",
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
}));
vi.mock("@/lib/auth-context", () => ({ useAuth: vi.fn() }));
vi.mock("@/api/client", async () => {
  const actual = await vi.importActual<typeof import("@/api/client")>("@/api/client");
  return { ...actual, api: { ...actual.api, workspaces: {
    ...actual.api.workspaces, get: vi.fn(), list: vi.fn(),
    checkins: { ...actual.api.workspaces.checkins, current: vi.fn(), list: vi.fn(), get: vi.fn(), startRound: vi.fn(), submit: vi.fn() },
    checkinTemplate: { get: vi.fn() }, checkinDimensions: { create: vi.fn(), update: vi.fn() },
  }, connections: { ...actual.api.connections, list: vi.fn() } } };
});

const overview: WorkspaceOverviewOut = {
  workspace: { id: "ws-1", connection_id: "conn-1", status: "ACTIVE", relationship_type: "PARTNER", created_at: "2026-01-01T00:00:00Z", dissolved_at: null },
  dual_profile: [{ user_id: "me", display_name: "Lukas", self_person: null, core_numbers: null }, { user_id: "them", display_name: "Ada", self_person: null, core_numbers: null }],
};

function renderPage() { return render(<LocaleProvider><WorkspaceCheckinsPage /></LocaleProvider>); }

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(useAuth).mockReturnValue({ status: "authenticated", user: { id: "me" }, error: null } as ReturnType<typeof useAuth>);
  vi.mocked(api.workspaces.get).mockResolvedValue(overview);
  vi.mocked(api.workspaces.list).mockResolvedValue([]);
  vi.mocked(api.connections.list).mockResolvedValue([]);
  vi.mocked(api.workspaces.checkins.current).mockResolvedValue(null);
  vi.mocked(api.workspaces.checkins.list).mockResolvedValue([]);
  vi.mocked(api.workspaces.checkinTemplate.get).mockResolvedValue({ id: "template-1", version: 1, active: true, dimensions: [] });
});

describe("WorkspaceCheckinsPage", () => {
  it("loads overview, current round, history and template into the check-in journey", async () => {
    renderPage();
    expect(await screen.findByRole("heading", { name: "Wie geht es euch miteinander?" })).toBeInTheDocument();
    expect(api.workspaces.checkins.current).toHaveBeenCalledWith("ws-1");
    expect(api.workspaces.checkins.list).toHaveBeenCalledWith("ws-1", { limit: 200, offset: 0 });
    expect(api.workspaces.checkinTemplate.get).toHaveBeenCalledWith("ws-1");
  });

  it("renders the check-in feature gate as a calm disabled state", async () => {
    vi.mocked(api.workspaces.checkins.current).mockRejectedValue(new ApiError("disabled", "V2_PHASE_DISABLED", 404));
    renderPage();
    expect(await screen.findByRole("heading", { name: "Check-ins sind noch nicht verfügbar" })).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });
});
