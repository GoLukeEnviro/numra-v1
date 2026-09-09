import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { EmailVerificationBanner } from "@/components/layout/email-verification-banner";
import { api, type UserOut } from "@/api/client";
import { LocaleProvider } from "@/i18n/context";
import { useAuth } from "@/lib/auth-context";

vi.mock("@/lib/auth-context", () => ({ useAuth: vi.fn() }));

vi.mock("@/api/client", async () => {
  const actual = await vi.importActual<typeof import("@/api/client")>("@/api/client");
  return { ...actual, api: { auth: { requestEmailVerification: vi.fn() } } };
});

function mockAuth(status: "authenticated" | "anonymous", user: UserOut | null) {
  vi.mocked(useAuth).mockReturnValue({
    status,
    user,
    error: null,
    login: vi.fn(),
    register: vi.fn(),
    logout: vi.fn(),
    refresh: vi.fn(),
  } as ReturnType<typeof useAuth>);
}

const unverifiedUser: UserOut = {
  id: "u1",
  email: "someone@example.com",
  role: "USER",
  is_active: true,
  email_verified_at: null,
};

const verifiedUser: UserOut = { ...unverifiedUser, email_verified_at: "2026-01-01T00:00:00Z" };

function renderBanner() {
  return render(
    <LocaleProvider>
      <EmailVerificationBanner />
    </LocaleProvider>,
  );
}

describe("EmailVerificationBanner", () => {
  beforeEach(() => {
    vi.mocked(api.auth.requestEmailVerification).mockReset();
  });

  it("renders nothing for an anonymous visitor", () => {
    mockAuth("anonymous", null);
    renderBanner();

    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });

  it("renders nothing once the user's email is verified", () => {
    mockAuth("authenticated", verifiedUser);
    renderBanner();

    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });

  it("renders for an authenticated user with an unverified email", () => {
    mockAuth("authenticated", unverifiedUser);
    renderBanner();

    expect(screen.getByRole("status")).toBeInTheDocument();
  });

  it("sends a new verification link and shows an inline success text", async () => {
    mockAuth("authenticated", unverifiedUser);
    vi.mocked(api.auth.requestEmailVerification).mockResolvedValue(undefined);
    renderBanner();

    fireEvent.click(screen.getByRole("button", { name: "Link erneut senden" }));

    expect(
      await screen.findByText("Ein neuer Bestätigungslink wurde gesendet."),
    ).toBeInTheDocument();
    expect(api.auth.requestEmailVerification).toHaveBeenCalledTimes(1);
  });

  it("can be dismissed locally", () => {
    mockAuth("authenticated", unverifiedUser);
    renderBanner();

    fireEvent.click(screen.getByRole("button", { name: "Ausblenden" }));

    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });
});
