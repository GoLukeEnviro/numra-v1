import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import CopilotPage from "@/app/copilot/page";
import { api, type UserConnectionOut, type WorkspaceSummaryOut } from "@/api/client";
import { LocaleProvider } from "@/i18n/context";
import { useAuth } from "@/lib/auth-context";

vi.mock("next/navigation", () => ({
  usePathname: () => "/copilot",
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
}));
vi.mock("@/lib/auth-context", () => ({ useAuth: vi.fn() }));
vi.mock("@/api/client", async () => {
  const actual = await vi.importActual<typeof import("@/api/client")>("@/api/client");
  return { ...actual, api: { workspaces: { list: vi.fn() }, connections: { list: vi.fn() } } };
});

const workspace = {
  id: "ws-1",
  connection_id: "conn-1",
  status: "ACTIVE",
  relationship_type: "PARTNER",
  created_at: "2026-01-01T00:00:00Z",
  dissolved_at: null,
} as WorkspaceSummaryOut;
const connection = {
  id: "conn-1",
  counterpart_user_id: "them",
  counterpart_display_name: "Ada Lovelace",
  status: "ACTIVE",
  created_at: "2026-01-01T00:00:00Z",
  dissolved_at: null,
} as UserConnectionOut;

function renderPage() {
  return render(<LocaleProvider><CopilotPage /></LocaleProvider>);
}

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(useAuth).mockReturnValue({ status: "authenticated", user: { id: "me" }, error: null } as ReturnType<typeof useAuth>);
});

describe("CopilotPage", () => {
  it("links active relationship workspaces directly to their copilot", async () => {
    vi.mocked(api.workspaces.list).mockResolvedValue([workspace]);
    vi.mocked(api.connections.list).mockResolvedValue([connection]);
    renderPage();

    expect(await screen.findByRole("heading", { name: "Copilot" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Ada Lovelace/ })).toHaveAttribute("href", "/workspaces/ws-1/copilot");
  });

  it("shows a relationship-workspace empty state without creating a personal thread", async () => {
    vi.mocked(api.workspaces.list).mockResolvedValue([]);
    vi.mocked(api.connections.list).mockResolvedValue([]);
    renderPage();

    expect(await screen.findByText("Noch kein Beziehungs-Copilot verfügbar")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Verbindungen ansehen" })).toHaveAttribute("href", "/connections");
  });
});
