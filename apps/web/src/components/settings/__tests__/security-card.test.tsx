import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { SecurityCard } from "@/components/settings/security-card";
import { api, ApiError } from "@/api/client";
import { LocaleProvider } from "@/i18n/context";

/**
 * PWA-08 targeted coverage: the security card is the auth-critical settings surface
 * (password change, session list, "log out other devices") and had no component test
 * at all. The assertions below are the branches that matter for a user in trouble:
 * a mismatch is caught locally, a rejected password change surfaces the backend's own
 * error code, a successful change says so, and the session list renders an error
 * state with a retry instead of an empty list.
 */
vi.mock("@/api/client", async () => {
  const actual = await vi.importActual<typeof import("@/api/client")>("@/api/client");
  return {
    ...actual,
    api: {
      auth: {
        changePassword: vi.fn(),
        sessions: vi.fn(),
        revokeOtherSessions: vi.fn(),
      },
    },
  };
});

const SESSION = {
  id: "11111111-1111-1111-1111-111111111111",
  created_at: "2026-09-19T10:00:00+00:00",
  expires_at: "2026-10-03T10:00:00+00:00",
  revoked_at: null,
  is_current: true,
};

function renderCard() {
  return render(
    <LocaleProvider>
      <SecurityCard />
    </LocaleProvider>,
  );
}

async function fillPasswordForm(current: string, next: string, confirm: string) {
  fireEvent.change(screen.getByLabelText("Aktuelles Passwort"), { target: { value: current } });
  fireEvent.change(screen.getByLabelText("Neues Passwort"), { target: { value: next } });
  fireEvent.change(screen.getByLabelText("Neues Passwort bestätigen"), { target: { value: confirm } });
  fireEvent.click(screen.getByRole("button", { name: /Passwort ändern/ }));
}

describe("SecurityCard", () => {
  beforeEach(() => {
    vi.mocked(api.auth.changePassword).mockReset();
    vi.mocked(api.auth.sessions).mockReset();
    vi.mocked(api.auth.sessions).mockResolvedValue([SESSION] as never);
    vi.mocked(api.auth.revokeOtherSessions).mockReset();
  });

  it("refuses a mismatch locally without calling the API", async () => {
    renderCard();

    await fillPasswordForm("alt-passwort-2026", "neues-passwort-2026", "anders-passwort-2026");

    expect(await screen.findByRole("alert")).toHaveTextContent("PASSWORD_MISMATCH");
    expect(api.auth.changePassword).not.toHaveBeenCalled();
  });

  it("surfaces the backend error code when the current password is wrong", async () => {
    vi.mocked(api.auth.changePassword).mockRejectedValue(
      new ApiError("current password did not match", "INVALID_CREDENTIALS", 401),
    );
    renderCard();

    await fillPasswordForm("falsch-passwort-2026", "neues-passwort-2026", "neues-passwort-2026");

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("INVALID_CREDENTIALS");
    expect(alert).toHaveTextContent("current password did not match");
  });

  it("confirms a successful change and clears the fields", async () => {
    vi.mocked(api.auth.changePassword).mockResolvedValue(undefined as never);
    renderCard();

    await fillPasswordForm("alt-passwort-2026", "neues-passwort-2026", "neues-passwort-2026");

    expect(await screen.findByText(/Passwort geändert/)).toBeInTheDocument();
    expect(screen.getByLabelText("Aktuelles Passwort")).toHaveValue("");
    expect(api.auth.changePassword).toHaveBeenCalledWith({
      current_password: "alt-passwort-2026",
      new_password: "neues-passwort-2026",
    });
  });

  it("renders the session list and offers logging out other devices", async () => {
    vi.mocked(api.auth.sessions).mockResolvedValue([
      SESSION,
      { ...SESSION, id: "22222222-2222-2222-2222-222222222222", is_current: false },
    ] as never);
    vi.mocked(api.auth.revokeOtherSessions).mockResolvedValue(undefined as never);
    renderCard();

    expect(await screen.findByText("Dieses Gerät")).toBeInTheDocument();
    expect(screen.getByText("Anderes Gerät")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /Andere Geräte abmelden/ }));

    await waitFor(() => expect(api.auth.revokeOtherSessions).toHaveBeenCalledTimes(1));
    expect(await screen.findByText("Andere Geräte wurden abgemeldet.")).toBeInTheDocument();
  });

  it("shows an error state with retry when the session list cannot be loaded", async () => {
    vi.mocked(api.auth.sessions)
      .mockRejectedValueOnce(new ApiError("offline", "NETWORK_ERROR", 0))
      .mockResolvedValueOnce([SESSION] as never);
    renderCard();

    expect(await screen.findByText("Sitzungen konnten nicht geladen werden")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Erneut versuchen" }));

    expect(await screen.findByText("Dieses Gerät")).toBeInTheDocument();
  });
});
