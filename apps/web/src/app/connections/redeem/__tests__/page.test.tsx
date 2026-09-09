import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import ConnectionsRedeemPage from "@/app/connections/redeem/page";
import { LocaleProvider } from "@/i18n/context";
import { useAuth } from "@/lib/auth-context";
import { api, ApiError } from "@/api/client";

const push = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push, replace: vi.fn() }),
  useSearchParams: () => new URLSearchParams("token=abc123"),
}));

vi.mock("@/lib/auth-context", () => ({ useAuth: vi.fn() }));

vi.mock("@/api/client", async () => {
  const actual = await vi.importActual<typeof import("@/api/client")>("@/api/client");
  return {
    ...actual,
    api: {
      connections: { previewByToken: vi.fn(), redeemInvitation: vi.fn(), declineInvitation: vi.fn() },
    },
  };
});

function renderPage() {
  return render(
    <LocaleProvider>
      <ConnectionsRedeemPage />
    </LocaleProvider>,
  );
}

const PREVIEW_LINK = { id: "invite-1", method: "LINK" as const, expires_at: "2026-09-20T00:00:00Z" };
const PREVIEW_EMAIL = { id: "invite-2", method: "EMAIL" as const, expires_at: "2026-09-20T00:00:00Z" };

beforeEach(() => {
  push.mockReset();
  vi.mocked(api.connections.previewByToken).mockReset();
  vi.mocked(api.connections.redeemInvitation).mockReset();
  vi.mocked(api.connections.declineInvitation).mockReset();
});

describe("ConnectionsRedeemPage", () => {
  it("renders method and expiry once the preview resolves", async () => {
    vi.mocked(useAuth).mockReturnValue({ status: "authenticated" } as never);
    vi.mocked(api.connections.previewByToken).mockResolvedValue(PREVIEW_LINK);
    renderPage();

    await waitFor(() => expect(screen.getByText("Link")).toBeInTheDocument());
    expect(api.connections.previewByToken).toHaveBeenCalledWith("abc123");
  });

  it("shows an invalid state without leaking inviter detail for an expired/invalid token", async () => {
    vi.mocked(useAuth).mockReturnValue({ status: "anonymous" } as never);
    vi.mocked(api.connections.previewByToken).mockRejectedValue(
      new ApiError("invalid", "INVITATION_EXPIRED_OR_INVALID", 400),
    );
    renderPage();

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "abgelaufen, bereits verwendet oder existiert nicht",
    );
  });

  it("navigates to the workspace consent route on accept", async () => {
    vi.mocked(useAuth).mockReturnValue({ status: "authenticated" } as never);
    vi.mocked(api.connections.previewByToken).mockResolvedValue(PREVIEW_LINK);
    vi.mocked(api.connections.redeemInvitation).mockResolvedValue({
      connection: {
        id: "conn-1",
        user_a_id: "a",
        user_b_id: "b",
        status: "ACTIVE",
        created_at: "2026-09-06T00:00:00Z",
        dissolved_at: null,
        counterpart_user_id: "a",
        counterpart_display_name: "Ada",
      },
      workspace_id: "workspace-1",
    });
    renderPage();

    await screen.findByText("Link");
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Annehmen" }));
    });

    expect(push).toHaveBeenCalledWith("/workspaces/workspace-1/consent?justConnected=1");
  });

  it("shows the decline button only for EMAIL invitations and declines using the preview id", async () => {
    vi.mocked(useAuth).mockReturnValue({ status: "authenticated" } as never);
    vi.mocked(api.connections.previewByToken).mockResolvedValue(PREVIEW_EMAIL);
    vi.mocked(api.connections.declineInvitation).mockResolvedValue({
      id: "invite-2",
      method: "EMAIL",
      invitee_email: "me@example.com",
      state: "DECLINED",
      expires_at: "2026-09-20T00:00:00Z",
      created_at: "2026-09-06T00:00:00Z",
    });
    renderPage();

    const declineButton = await screen.findByRole("button", { name: "Ablehnen" });
    await act(async () => {
      fireEvent.click(declineButton);
    });

    expect(api.connections.declineInvitation).toHaveBeenCalledWith("invite-2");
    expect(await screen.findByText("Einladung abgelehnt")).toBeInTheDocument();
  });

  it("hides the decline button for LINK invitations", async () => {
    vi.mocked(useAuth).mockReturnValue({ status: "authenticated" } as never);
    vi.mocked(api.connections.previewByToken).mockResolvedValue(PREVIEW_LINK);
    renderPage();

    await screen.findByText("Link");
    expect(screen.queryByRole("button", { name: "Ablehnen" })).not.toBeInTheDocument();
  });

  it("prevents a second accept click from firing a second request", async () => {
    vi.mocked(useAuth).mockReturnValue({ status: "authenticated" } as never);
    vi.mocked(api.connections.previewByToken).mockResolvedValue(PREVIEW_LINK);
    let resolveRedeem: (value: unknown) => void = () => {};
    vi.mocked(api.connections.redeemInvitation).mockReturnValue(
      new Promise((resolve) => {
        resolveRedeem = resolve;
      }) as never,
    );
    renderPage();

    const acceptButton = await screen.findByRole("button", { name: "Annehmen" });
    fireEvent.click(acceptButton);
    fireEvent.click(acceptButton);

    expect(api.connections.redeemInvitation).toHaveBeenCalledTimes(1);
    await act(async () => {
      resolveRedeem({
        connection: {
          id: "conn-1",
          user_a_id: "a",
          user_b_id: "b",
          status: "ACTIVE",
          created_at: "2026-09-06T00:00:00Z",
          dissolved_at: null,
          counterpart_user_id: "a",
          counterpart_display_name: "Ada",
        },
        workspace_id: "workspace-1",
      });
    });
  });
});
