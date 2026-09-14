import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import ConnectionsPage from "@/app/connections/page";
import { LocaleProvider } from "@/i18n/context";
import { useAuth } from "@/lib/auth-context";
import { ApiError, api } from "@/api/client";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  usePathname: () => "/connections",
}));

vi.mock("@/lib/auth-context", () => ({ useAuth: vi.fn() }));

vi.mock("@/api/client", async () => {
  const actual = await vi.importActual<typeof import("@/api/client")>("@/api/client");
  return {
    ...actual,
    api: {
      connections: { list: vi.fn(), listInvitations: vi.fn(), dissolve: vi.fn(), revokeInvitation: vi.fn() },
      workspaces: { list: vi.fn() },
    },
  };
});

function renderPage() {
  return render(
    <LocaleProvider>
      <ConnectionsPage />
    </LocaleProvider>,
  );
}

const CONNECTION = {
  id: "conn-1",
  user_a_id: "user-1",
  user_b_id: "user-2",
  status: "ACTIVE" as const,
  created_at: "2026-09-01T00:00:00Z",
  dissolved_at: null,
  counterpart_user_id: "user-2",
  counterpart_display_name: "Ada Lovelace",
};

function invitation(state: "PENDING" | "EXPIRED" | "DECLINED" | "REVOKED", id: string) {
  return {
    id,
    method: "LINK" as const,
    invitee_email: null,
    state,
    expires_at: "2026-09-20T00:00:00Z",
    created_at: "2026-09-06T00:00:00Z",
  };
}

beforeEach(() => {
  vi.mocked(useAuth).mockReturnValue({
    status: "authenticated",
    user: { id: "user-1", email: "me@example.com", role: "USER", is_active: true } as never,
    error: null,
    login: vi.fn(),
    register: vi.fn(),
    logout: vi.fn(),
    refresh: vi.fn(),
  });
  vi.mocked(api.connections.list).mockReset();
  vi.mocked(api.connections.listInvitations).mockReset();
  vi.mocked(api.connections.revokeInvitation).mockReset();
  vi.mocked(api.connections.dissolve).mockReset();
  vi.mocked(api.workspaces.list).mockReset().mockResolvedValue([]);
});

describe("ConnectionsPage", () => {
  it("shows the empty state with an invite CTA when no connections exist", async () => {
    vi.mocked(api.connections.list).mockResolvedValue([]);
    vi.mocked(api.connections.listInvitations).mockResolvedValue([]);
    renderPage();

    expect(await screen.findByText("Noch keine Verbindungen")).toBeInTheDocument();
  });

  it("renders mixed invitation states simultaneously with neutral badges", async () => {
    vi.mocked(api.connections.list).mockResolvedValue([]);
    vi.mocked(api.connections.listInvitations).mockResolvedValue([
      invitation("PENDING", "inv-1"),
      invitation("EXPIRED", "inv-2"),
      invitation("REVOKED", "inv-3"),
      invitation("DECLINED", "inv-4"),
    ]);
    renderPage();

    expect(await screen.findByText("Ausstehend")).toBeInTheDocument();
    expect(screen.getByText("Abgelaufen")).toBeInTheDocument();
    expect(screen.getByText("Zurückgezogen")).toBeInTheDocument();
    expect(screen.getByText("Abgelehnt")).toBeInTheDocument();
  });

  it("revokes a pending invitation through the inline confirm and updates the list", async () => {
    vi.mocked(api.connections.list).mockResolvedValue([]);
    vi.mocked(api.connections.listInvitations).mockResolvedValue([invitation("PENDING", "inv-1")]);
    vi.mocked(api.connections.revokeInvitation).mockResolvedValue({ ...invitation("REVOKED", "inv-1") });
    renderPage();

    await screen.findByText("Ausstehend");
    fireEvent.click(screen.getByRole("button", { name: "Zurückziehen" }));
    const confirmButton = await screen.findByRole("button", { name: "Endgültig zurückziehen" });
    await act(async () => {
      fireEvent.click(confirmButton);
    });

    expect(api.connections.revokeInvitation).toHaveBeenCalledWith("inv-1");
    await waitFor(() => expect(screen.getByText("Noch keine Einladungen versendet")).toBeInTheDocument());
  });

  it("shows the counterpart name from the connection contract for active connections", async () => {
    vi.mocked(api.connections.list).mockResolvedValue([CONNECTION]);
    vi.mocked(api.connections.listInvitations).mockResolvedValue([]);
    renderPage();

    expect(await screen.findByText("Ada Lovelace")).toBeInTheDocument();
  });

  it("moves a dissolved connection into retained history and keeps its workspace reachable", async () => {
    vi.mocked(api.connections.list).mockResolvedValue([CONNECTION]);
    vi.mocked(api.connections.listInvitations).mockResolvedValue([]);
    vi.mocked(api.workspaces.list).mockResolvedValue([{
      id: "ws-1", connection_id: CONNECTION.id, status: "ACTIVE", relationship_type: "PARTNER",
      created_at: "2026-09-01T00:00:00Z", dissolved_at: null,
    }]);
    vi.mocked(api.connections.dissolve).mockResolvedValue({
      ...CONNECTION, status: "DISSOLVED", dissolved_at: "2026-09-12T10:00:00Z",
    });
    renderPage();

    await screen.findByText("Ada Lovelace");
    fireEvent.click(screen.getByRole("button", { name: "Verbindung auflösen" }));
    fireEvent.click(screen.getByRole("button", { name: "Endgültig auflösen" }));

    expect(await screen.findByRole("heading", { name: "Historische Verbindungen" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Historischen Workspace öffnen" })).toHaveAttribute("href", "/workspaces/ws-1");
    expect(screen.queryByRole("button", { name: "Verbindung auflösen" })).not.toBeInTheDocument();
  });

  it("keeps a connection actionable and shows an alert when dissolution fails", async () => {
    vi.mocked(api.connections.list).mockResolvedValue([CONNECTION]);
    vi.mocked(api.connections.listInvitations).mockResolvedValue([]);
    vi.mocked(api.connections.dissolve).mockRejectedValue(new ApiError("Auflösung blockiert", "CONFLICT", 409));
    renderPage();

    await screen.findByText("Ada Lovelace");
    fireEvent.click(screen.getByRole("button", { name: "Verbindung auflösen" }));
    fireEvent.click(screen.getByRole("button", { name: "Endgültig auflösen" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Auflösung blockiert");
    expect(screen.getByRole("button", { name: "Verbindung auflösen" })).toBeInTheDocument();
  });

  it("shows a retryable error when retained workspace links cannot be loaded", async () => {
    vi.mocked(api.connections.list).mockResolvedValue([{ ...CONNECTION, status: "DISSOLVED", dissolved_at: "2026-09-12T10:00:00Z" }]);
    vi.mocked(api.connections.listInvitations).mockResolvedValue([]);
    vi.mocked(api.workspaces.list).mockRejectedValue(new Error("Workspace-Zuordnung nicht verfügbar"));
    renderPage();

    expect(await screen.findByRole("alert")).toHaveTextContent("Workspace-Zuordnung nicht verfügbar");
    expect(screen.getByText("Ada Lovelace")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Try again" })).toBeInTheDocument();
  });
});
