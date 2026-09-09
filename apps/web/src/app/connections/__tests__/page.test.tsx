import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import ConnectionsPage from "@/app/connections/page";
import { LocaleProvider } from "@/i18n/context";
import { useAuth } from "@/lib/auth-context";
import { api } from "@/api/client";

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
});
