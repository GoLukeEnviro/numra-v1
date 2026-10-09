import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AgeConfirmationBanner } from "@/components/layout/age-confirmation-banner";
import { api, type UserOut } from "@/api/client";
import { LocaleProvider } from "@/i18n/context";
import { useAuth } from "@/lib/auth-context";

vi.mock("@/lib/auth-context", () => ({ useAuth: vi.fn() }));

vi.mock("@/api/client", async () => {
  const actual = await vi.importActual<typeof import("@/api/client")>("@/api/client");
  return { ...actual, api: { auth: { confirmAge: vi.fn() } } };
});

const refresh = vi.fn();

function mockAuth(status: "authenticated" | "anonymous", user: UserOut | null) {
  vi.mocked(useAuth).mockReturnValue({
    status,
    user,
    error: null,
    login: vi.fn(),
    register: vi.fn(),
    logout: vi.fn(),
    refresh,
  } as ReturnType<typeof useAuth>);
}

const legacyUser: UserOut = {
  id: "u1",
  email: "someone@example.com",
  role: "USER",
  is_active: true,
  email_verified_at: "2026-01-01T00:00:00Z",
  age_confirmed_at: null,
};

const confirmedUser: UserOut = { ...legacyUser, age_confirmed_at: "2026-10-09T10:00:00Z" };

function renderBanner() {
  return render(
    <LocaleProvider>
      <AgeConfirmationBanner />
    </LocaleProvider>,
  );
}

describe("AgeConfirmationBanner", () => {
  beforeEach(() => {
    vi.mocked(api.auth.confirmAge).mockReset();
    refresh.mockReset();
  });

  it("renders nothing for an anonymous visitor", () => {
    mockAuth("anonymous", null);
    renderBanner();

    expect(screen.queryByRole("region")).not.toBeInTheDocument();
  });

  it("renders nothing once the age is confirmed", () => {
    mockAuth("authenticated", confirmedUser);
    renderBanner();

    expect(screen.queryByRole("region")).not.toBeInTheDocument();
  });

  it("shows an unchecked checkbox for an unconfirmed legacy account", () => {
    mockAuth("authenticated", legacyUser);
    renderBanner();

    expect(screen.getByRole("region")).toBeInTheDocument();
    expect(screen.getByLabelText("Ich bin mindestens 18 Jahre alt.")).not.toBeChecked();
  });

  it("does not call the API until the box is ticked", () => {
    mockAuth("authenticated", legacyUser);
    renderBanner();

    fireEvent.click(screen.getByRole("button", { name: "Bestätigen" }));

    expect(screen.getByText("Bitte setze zuerst das Häkchen.")).toBeInTheDocument();
    expect(api.auth.confirmAge).not.toHaveBeenCalled();
  });

  it("confirms and refreshes the profile after ticking the box", async () => {
    vi.mocked(api.auth.confirmAge).mockResolvedValue(confirmedUser);
    mockAuth("authenticated", legacyUser);
    renderBanner();

    fireEvent.click(screen.getByLabelText("Ich bin mindestens 18 Jahre alt."));
    fireEvent.click(screen.getByRole("button", { name: "Bestätigen" }));

    await waitFor(() => expect(api.auth.confirmAge).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(refresh).toHaveBeenCalledTimes(1));
  });

  it("shows an error and keeps the banner when saving fails", async () => {
    vi.mocked(api.auth.confirmAge).mockRejectedValue(new Error("boom"));
    mockAuth("authenticated", legacyUser);
    renderBanner();

    fireEvent.click(screen.getByLabelText("Ich bin mindestens 18 Jahre alt."));
    fireEvent.click(screen.getByRole("button", { name: "Bestätigen" }));

    expect(
      await screen.findByText(
        "Die Bestätigung konnte nicht gespeichert werden. Bitte versuche es erneut.",
      ),
    ).toBeInTheDocument();
    expect(refresh).not.toHaveBeenCalled();
    expect(screen.getByRole("region")).toBeInTheDocument();
  });
});
