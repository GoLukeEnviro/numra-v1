import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import VerifyEmailPage from "@/app/verify-email/page";
import { api, ApiError } from "@/api/client";
import { LocaleProvider } from "@/i18n/context";
import { useAuth } from "@/lib/auth-context";

let currentToken: string | null = "valid-token";

vi.mock("next/navigation", () => ({
  useSearchParams: () => ({ get: (key: string) => (key === "token" ? currentToken : null) }),
}));

vi.mock("@/lib/auth-context", () => ({ useAuth: vi.fn() }));

vi.mock("@/api/client", async () => {
  const actual = await vi.importActual<typeof import("@/api/client")>("@/api/client");
  return {
    ...actual,
    api: { auth: { verifyEmail: vi.fn(), requestEmailVerification: vi.fn() } },
  };
});

function mockAuth(status: "authenticated" | "anonymous") {
  vi.mocked(useAuth).mockReturnValue({
    status,
    user:
      status === "authenticated"
        ? { id: "u1", email: "someone@example.com", role: "USER", is_active: true }
        : null,
    error: null,
    login: vi.fn(),
    register: vi.fn(),
    logout: vi.fn(),
    refresh: vi.fn(),
  } as ReturnType<typeof useAuth>);
}

function renderPage() {
  return render(
    <LocaleProvider>
      <VerifyEmailPage />
    </LocaleProvider>,
  );
}

describe("Verify email page", () => {
  beforeEach(() => {
    vi.mocked(api.auth.verifyEmail).mockReset();
    vi.mocked(api.auth.requestEmailVerification).mockReset();
    currentToken = "valid-token";
    mockAuth("anonymous");
  });

  it("shows the missing-token state and never calls the API when ?token= is absent", async () => {
    currentToken = null;
    renderPage();

    expect(
      await screen.findByText("Dieser Link enthält kein gültiges Token."),
    ).toBeInTheDocument();
    expect(api.auth.verifyEmail).not.toHaveBeenCalled();
  });

  it("calls verifyEmail exactly once and shows the login CTA for a signed-out success", async () => {
    vi.mocked(api.auth.verifyEmail).mockResolvedValue(undefined);
    renderPage();

    expect(await screen.findByText("E-Mail bestätigt")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Zum Login" })).toHaveAttribute("href", "/login");
    expect(api.auth.verifyEmail).toHaveBeenCalledTimes(1);
    expect(api.auth.verifyEmail).toHaveBeenCalledWith({ token: "valid-token" });
  });

  it("shows the dashboard CTA for a signed-in success", async () => {
    mockAuth("authenticated");
    vi.mocked(api.auth.verifyEmail).mockResolvedValue(undefined);
    renderPage();

    expect(await screen.findByText("E-Mail bestätigt")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Zur Übersicht" })).toHaveAttribute(
      "href",
      "/dashboard",
    );
  });

  it("offers a resend button for a signed-in user on an invalid token, not a login link", async () => {
    mockAuth("authenticated");
    vi.mocked(api.auth.verifyEmail).mockRejectedValue(
      new ApiError("bad token", "INVALID_OR_EXPIRED_TOKEN", 400),
    );
    vi.mocked(api.auth.requestEmailVerification).mockResolvedValue(undefined);
    renderPage();

    const resendButton = await screen.findByRole("button", {
      name: "Neuen Bestätigungslink senden",
    });
    expect(screen.queryByRole("link", { name: "Zum Login" })).not.toBeInTheDocument();

    fireEvent.click(resendButton);

    expect(
      await screen.findByText("Ein neuer Bestätigungslink wurde gesendet."),
    ).toBeInTheDocument();
    expect(api.auth.requestEmailVerification).toHaveBeenCalledTimes(1);
  });

  it("offers only a login link for a signed-out user on an invalid token, no resend button", async () => {
    vi.mocked(api.auth.verifyEmail).mockRejectedValue(
      new ApiError("bad token", "INVALID_OR_EXPIRED_TOKEN", 400),
    );
    renderPage();

    expect(await screen.findByRole("link", { name: "Zum Login" })).toHaveAttribute(
      "href",
      "/login",
    );
    expect(
      screen.queryByRole("button", { name: "Neuen Bestätigungslink senden" }),
    ).not.toBeInTheDocument();
  });

  it("shows a rate-limit message on 429", async () => {
    vi.mocked(api.auth.verifyEmail).mockRejectedValue(
      new ApiError("too many", "RATE_LIMIT_EXCEEDED", 429),
    );
    renderPage();

    expect(
      await screen.findByText("Zu viele Versuche. Bitte versuche es später erneut."),
    ).toBeInTheDocument();
  });
});
