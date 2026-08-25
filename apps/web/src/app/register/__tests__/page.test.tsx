import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import RegisterPage from "@/app/register/page";
import { api, ApiError, type PublicConfigOut } from "@/api/client";
import { LocaleProvider } from "@/i18n/context";
import { useAuth } from "@/lib/auth-context";

const replace = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace, push: vi.fn() }),
}));

vi.mock("@/lib/auth-context", () => ({ useAuth: vi.fn() }));

vi.mock("@/api/client", async () => {
  const actual = await vi.importActual<typeof import("@/api/client")>("@/api/client");
  return { ...actual, api: { publicConfig: { get: vi.fn() } } };
});

const openConfig: PublicConfigOut = {
  app_name: "Numra",
  self_signup_enabled: true,
  supported_ui_locales: ["de", "en"],
};

const closedConfig: PublicConfigOut = {
  ...openConfig,
  self_signup_enabled: false,
};

function mockAuth(registerFn = vi.fn()) {
  vi.mocked(useAuth).mockReturnValue({
    status: "anonymous",
    user: null,
    error: null,
    login: vi.fn(),
    register: registerFn,
    logout: vi.fn(),
    refresh: vi.fn(),
  } as ReturnType<typeof useAuth>);
  return registerFn;
}

function renderPage() {
  return render(
    <LocaleProvider>
      <RegisterPage />
    </LocaleProvider>,
  );
}

async function fillAndSubmit(password: string, confirm: string) {
  fireEvent.change(await screen.findByLabelText("E-Mail"), {
    target: { value: "ada@example.com" },
  });
  fireEvent.change(screen.getByLabelText("Passwort"), { target: { value: password } });
  fireEvent.change(screen.getByLabelText("Passwort bestätigen"), { target: { value: confirm } });
  fireEvent.click(screen.getByRole("button", { name: "Konto erstellen" }));
}

describe("Register page", () => {
  beforeEach(() => {
    vi.mocked(api.publicConfig.get).mockReset();
    replace.mockReset();
  });

  it("registers and navigates to /onboarding on success", async () => {
    vi.mocked(api.publicConfig.get).mockResolvedValue(openConfig);
    const registerFn = mockAuth(vi.fn().mockResolvedValue(undefined));
    renderPage();

    await fillAndSubmit("a-strong-password", "a-strong-password");

    await waitFor(() =>
      expect(registerFn).toHaveBeenCalledWith("ada@example.com", "a-strong-password"),
    );
    await waitFor(() => expect(replace).toHaveBeenCalledWith("/onboarding"));
  });

  it("renders no functional submit element when self-signup is disabled", async () => {
    vi.mocked(api.publicConfig.get).mockResolvedValue(closedConfig);
    mockAuth();
    renderPage();

    expect(await screen.findByText("Registrierung derzeit geschlossen.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Konto erstellen" })).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Zum Login" })).toBeInTheDocument();
  });

  it("shows a localized error for a duplicate email (409)", async () => {
    vi.mocked(api.publicConfig.get).mockResolvedValue(openConfig);
    const registerFn = mockAuth(
      vi.fn().mockRejectedValue(new ApiError("dup", "EMAIL_ALREADY_REGISTERED", 409)),
    );
    renderPage();

    await fillAndSubmit("a-strong-password", "a-strong-password");

    expect(registerFn).toHaveBeenCalled();
    expect(
      await screen.findByText("Für diese E-Mail-Adresse existiert bereits ein Konto."),
    ).toBeInTheDocument();
  });

  it("blocks submission client-side when the passwords do not match", async () => {
    vi.mocked(api.publicConfig.get).mockResolvedValue(openConfig);
    const registerFn = mockAuth();
    renderPage();

    await fillAndSubmit("a-strong-password", "a-different-password");

    expect(await screen.findByText("Die Passwörter stimmen nicht überein.")).toBeInTheDocument();
    expect(registerFn).not.toHaveBeenCalled();
  });
});
