import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import ForgotPasswordPage from "@/app/forgot-password/page";
import { api, ApiError } from "@/api/client";
import { LocaleProvider } from "@/i18n/context";

vi.mock("@/api/client", async () => {
  const actual = await vi.importActual<typeof import("@/api/client")>("@/api/client");
  return { ...actual, api: { auth: { forgotPassword: vi.fn() } } };
});

function renderPage() {
  return render(
    <LocaleProvider>
      <ForgotPasswordPage />
    </LocaleProvider>,
  );
}

async function fillAndSubmit(email = "someone@example.com") {
  fireEvent.change(await screen.findByLabelText("E-Mail"), { target: { value: email } });
  fireEvent.click(screen.getByRole("button", { name: "Link anfordern" }));
}

describe("Forgot password page", () => {
  beforeEach(() => {
    vi.mocked(api.auth.forgotPassword).mockReset();
  });

  it("shows the same conditional success message regardless of whether the address exists", async () => {
    vi.mocked(api.auth.forgotPassword).mockResolvedValue(undefined);
    renderPage();

    await fillAndSubmit();

    expect(
      await screen.findByText(
        "Falls ein Konto mit dieser Adresse existiert, haben wir einen Link zum Zurücksetzen gesendet.",
      ),
    ).toBeInTheDocument();
    // Anti-enumeration: the copy never claims an email was actually sent.
    expect(screen.queryByText(/^Wir haben eine E-Mail gesendet/)).not.toBeInTheDocument();
  });

  it("does not redirect after a successful submission", async () => {
    vi.mocked(api.auth.forgotPassword).mockResolvedValue(undefined);
    renderPage();

    await fillAndSubmit();

    await waitFor(() => expect(api.auth.forgotPassword).toHaveBeenCalled());
    expect(screen.getByRole("link", { name: "Zurück zum Login" })).toHaveAttribute(
      "href",
      "/login",
    );
  });

  it("shows a rate-limit message on 429 and stays on the form", async () => {
    vi.mocked(api.auth.forgotPassword).mockRejectedValue(
      new ApiError("too many", "RATE_LIMIT_EXCEEDED", 429),
    );
    renderPage();

    await fillAndSubmit();

    expect(
      await screen.findByText("Zu viele Versuche. Bitte versuche es später erneut."),
    ).toBeInTheDocument();
    expect(screen.getByLabelText("E-Mail")).toBeInTheDocument();
  });
});
