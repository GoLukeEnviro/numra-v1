import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import ConnectionsInvitePage from "@/app/connections/invite/page";
import { LocaleProvider } from "@/i18n/context";
import { useAuth } from "@/lib/auth-context";
import { api } from "@/api/client";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  usePathname: () => "/connections/invite",
}));

vi.mock("@/lib/auth-context", () => ({ useAuth: vi.fn() }));

vi.mock("@/api/client", async () => {
  const actual = await vi.importActual<typeof import("@/api/client")>("@/api/client");
  return {
    ...actual,
    api: { connections: { invite: vi.fn() }, people: { list: vi.fn() } },
  };
});

function renderPage() {
  return render(
    <LocaleProvider>
      <ConnectionsInvitePage />
    </LocaleProvider>,
  );
}

beforeEach(() => {
  vi.mocked(api.connections.invite).mockReset();
  vi.mocked(api.people.list).mockReset();
  vi.mocked(useAuth).mockReturnValue({
    status: "authenticated",
    user: { id: "user-1", email: "me@example.com", role: "USER", is_active: true } as never,
    error: null,
    login: vi.fn(),
    register: vi.fn(),
    logout: vi.fn(),
    refresh: vi.fn(),
  });
  vi.mocked(api.people.list).mockResolvedValue([]);
});

const LINK_RESULT = {
  id: "invite-1",
  method: "LINK" as const,
  invitee_email: null,
  state: "PENDING" as const,
  expires_at: "2026-09-20T00:00:00Z",
  created_at: "2026-09-06T00:00:00Z",
  token: "plaintext-token",
  redeem_url: "https://app.example.com/connections/redeem?token=plaintext-token",
};

describe("ConnectionsInvitePage", () => {
  it("creates a LINK invitation with the correct request body", async () => {
    vi.mocked(api.connections.invite).mockResolvedValue(LINK_RESULT);
    renderPage();

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Weiter" }));
    });

    expect(api.connections.invite).toHaveBeenCalledWith({ method: "LINK" });
    expect(screen.getByDisplayValue(/redeem\?token=plaintext-token/)).toBeInTheDocument();
  });

  it("creates an EMAIL invitation with the entered address", async () => {
    vi.mocked(api.connections.invite).mockResolvedValue({
      ...LINK_RESULT,
      id: "invite-2",
      method: "EMAIL",
      invitee_email: "friend@example.com",
    });
    renderPage();

    fireEvent.click(screen.getByText("E-Mail"));
    fireEvent.change(screen.getByLabelText("E-Mail-Adresse"), {
      target: { value: "friend@example.com" },
    });
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Weiter" }));
    });

    expect(api.connections.invite).toHaveBeenCalledWith({
      method: "EMAIL",
      invitee_email: "friend@example.com",
    });
  });

  it("shows the short code separately for CODE invitations", async () => {
    vi.mocked(api.connections.invite).mockResolvedValue({
      ...LINK_RESULT,
      id: "invite-3",
      method: "CODE",
      token: "SHORT123",
      redeem_url: "https://app.example.com/connections/redeem?token=SHORT123",
    });
    renderPage();

    fireEvent.click(screen.getByText("Code"));
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Weiter" }));
    });

    expect(screen.getByDisplayValue("SHORT123")).toBeInTheDocument();
    expect(screen.getByDisplayValue(/redeem\?token=SHORT123/)).toBeInTheDocument();
  });

  it("copies the token and does not re-fetch it after a simulated remount", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.assign(navigator, { clipboard: { writeText } });
    vi.mocked(api.connections.invite).mockResolvedValue({ ...LINK_RESULT, id: "invite-4" });
    const { unmount } = renderPage();

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Weiter" }));
    });
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /Kopieren/ }));
    });
    expect(writeText).toHaveBeenCalledWith(LINK_RESULT.redeem_url);
    await waitFor(() => expect(screen.getByText("Kopiert!")).toBeInTheDocument());

    unmount();
    renderPage();
    expect(api.connections.invite).toHaveBeenCalledTimes(1);
    expect(screen.queryByDisplayValue(/plaintext-token/)).not.toBeInTheDocument();
  });

  it("prevents a second submit while the first request is in flight", async () => {
    let resolveInvite: (value: unknown) => void = () => {};
    vi.mocked(api.connections.invite).mockReturnValue(
      new Promise((resolve) => {
        resolveInvite = resolve;
      }) as never,
    );
    renderPage();

    const submit = screen.getByRole("button", { name: "Weiter" });
    fireEvent.click(submit);
    fireEvent.click(submit);

    expect(api.connections.invite).toHaveBeenCalledTimes(1);
    await act(async () => {
      resolveInvite(LINK_RESULT);
    });
  });

  it("never calls api.people.list -- no managed-profile connection UI", async () => {
    renderPage();
    await waitFor(() => expect(api.people.list).not.toHaveBeenCalled());
  });
});
