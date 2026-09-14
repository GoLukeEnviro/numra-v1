import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import Page from "@/app/workspaces/[id]/copilot/page";
import { ApiError, api, type WorkspaceOverviewOut } from "@/api/client";
import { LocaleProvider } from "@/i18n/context";
import { useAuth } from "@/lib/auth-context";

vi.mock("next/navigation", () => ({
  useParams: () => ({ id: "ws-1" }),
  usePathname: () => "/workspaces/ws-1/copilot",
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
}));
vi.mock("@/lib/auth-context", () => ({ useAuth: vi.fn() }));
vi.mock("@/api/client", async () => {
  const actual = await vi.importActual<typeof import("@/api/client")>("@/api/client");
  return { ...actual, api: { ...actual.api, workspaces: { ...actual.api.workspaces, get: vi.fn(), list: vi.fn(), copilot: { threads: { list: vi.fn(), create: vi.fn(), get: vi.fn(), archive: vi.fn(), messages: { list: vi.fn(), post: vi.fn() } } } }, connections: { ...actual.api.connections, list: vi.fn() } } };
});

const overview = {
  workspace: { id: "ws-1", connection_id: "conn-1", status: "ACTIVE", relationship_type: "PARTNER", created_at: "2026-01-01T00:00:00Z", dissolved_at: null },
  dual_profile: [{ user_id: "me", display_name: "Lukas", self_person: null, core_numbers: null }, { user_id: "them", display_name: "Ada", self_person: null, core_numbers: null }],
} as WorkspaceOverviewOut;

describe("WorkspaceCopilotPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(useAuth).mockReturnValue({ status: "authenticated", user: { id: "me" }, error: null } as ReturnType<typeof useAuth>);
    vi.mocked(api.workspaces.get).mockResolvedValue(overview);
    vi.mocked(api.workspaces.list).mockResolvedValue([]);
    vi.mocked(api.connections.list).mockResolvedValue([]);
    vi.mocked(api.workspaces.copilot.threads.list).mockResolvedValue([]);
    vi.mocked(api.workspaces.copilot.threads.create).mockResolvedValue({ id: "thread-1", workspace_id: "ws-1", owner_user_id: null, scope: "RELATIONSHIP_SHARED", context_version: 1, created_at: "2026-01-01T00:00:00Z", archived_at: null });
    vi.mocked(api.workspaces.copilot.threads.messages.list).mockResolvedValue([]);
  });

  it("loads the workspace and renders the relationship copilot", async () => {
    render(<LocaleProvider><Page /></LocaleProvider>);
    expect(await screen.findByRole("heading", { name: "Beziehungs-Copilot" })).toBeInTheDocument();
    expect(api.workspaces.get).toHaveBeenCalledWith("ws-1");
  });

  it("renders the calm disabled state when the Copilot endpoint is phase-gated", async () => {
    vi.mocked(api.workspaces.copilot.threads.list).mockRejectedValue(
      new ApiError("Copilot disabled", "V2_PHASE_DISABLED", 409),
    );

    render(<LocaleProvider><Page /></LocaleProvider>);

    expect(await screen.findByText("Copilot noch nicht verfügbar")).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });
});
