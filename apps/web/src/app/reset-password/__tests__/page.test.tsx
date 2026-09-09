import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import ResetPasswordPage from "@/app/reset-password/page";
import { api, ApiError } from "@/api/client";
import { LocaleProvider } from "@/i18n/context";

let currentToken: string | null = "valid-token";

vi.mock("next/navigation", () => ({
  useSearchParams: () => ({ get: (key: string) => (key === "token" ? currentToken : null) }),
}));

vi.mock("@/api/client", async () => {
  const actual = await vi.importActual<typeof import("@/api/client")>("@/api/client");
  return { ...actual, api: { auth: { resetPassword: vi.fn() } } };
});

function renderPage() {
  return render(
    <LocaleProvider>
      <ResetPasswordPage />
    </LocaleProvider>,
  );
}

async function fillAndSubmit(password: string, confirm: string) {
  fireEvent.change(await screen.findByLabelText("Neues Passwort"), {
    target: { value: password },
  });
  fireEvent.change(screen.getByLabelText("Neues Passwort bestätigen"), {
    target: { value: confirm },
  });
  fireEvent.click(screen.getByRole("button", { name: "Passwort festlegen" }));
}

describe("Reset password page", () => {
  beforeEach(() => {
    vi.mocked(api.auth.resetPassword).mockReset();
    currentToken = "valid-token";
  });

  it("shows the missing-token state and never calls the API when ?token= is absent", async () => {
    currentToken = null;
    renderPage();

    expect(
      await screen.findByText("Dieser Link enthält kein gültiges Token. Fordere einen neuen Link an."),
    ).toBeInTheDocument();
    expect(api.auth.resetPassword).not.toHaveBeenCalled();
  });

  it("blocks submission client-side on a too-short password", async () => {
    renderPage();
    await fillAndSubmit("short", "short");

    expect(
      await screen.findByText("Das Passwort muss mindestens 12 Zeichen lang sein."),
    ).toBeInTheDocument();
    expect(api.auth.resetPassword).not.toHaveBeenCalled();
  });

  it("blocks submission client-side on a password mismatch", async () => {
    renderPage();
    await fillAndSubmit("a-strong-password", "a-different-password");

    expect(await screen.findByText("Die Passwörter stimmen nicht überein.")).toBeInTheDocument();
    expect(api.auth.resetPassword).not.toHaveBeenCalled();
  });

  it("shows the success state with the sign-out explanation and a login CTA", async () => {
    vi.mocked(api.auth.resetPassword).mockResolvedValue(undefined);
    renderPage();
    await fillAndSubmit("a-strong-password", "a-strong-password");

    expect(
      await screen.findByText(
        "Passwort wurde geändert. Alle Sitzungen wurden abgemeldet — bitte melde dich erneut an.",
      ),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Zum Login" })).toHaveAttribute("href", "/login");
  });

  it("shows a neutral token-invalid state on INVALID_OR_EXPIRED_TOKEN, without distinguishing why", async () => {
    vi.mocked(api.auth.resetPassword).mockRejectedValue(
      new ApiError("bad token", "INVALID_OR_EXPIRED_TOKEN", 400),
    );
    renderPage();
    await fillAndSubmit("a-strong-password", "a-strong-password");

    const status = await screen.findByRole("status");
    expect(status).toHaveTextContent("Link nicht mehr gültig");
    expect(screen.getByRole("link", { name: "Neuen Link anfordern" })).toHaveAttribute(
      "href",
      "/forgot-password",
    );
  });

  it("shows a rate-limit message on 429", async () => {
    vi.mocked(api.auth.resetPassword).mockRejectedValue(
      new ApiError("too many", "RATE_LIMIT_EXCEEDED", 429),
    );
    renderPage();
    await fillAndSubmit("a-strong-password", "a-strong-password");

    expect(
      await screen.findByText("Zu viele Versuche. Bitte versuche es später erneut."),
    ).toBeInTheDocument();
  });
});
