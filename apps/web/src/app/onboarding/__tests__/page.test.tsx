import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import OnboardingPage from "@/app/onboarding/page";
import { api, type PersonOut } from "@/api/client";
import { LocaleProvider } from "@/i18n/context";
import { useAuth } from "@/lib/auth-context";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: vi.fn(), push: vi.fn() }),
}));

vi.mock("@/lib/auth-context", () => ({ useAuth: vi.fn() }));

vi.mock("@/api/client", async () => {
  const actual = await vi.importActual<typeof import("@/api/client")>("@/api/client");
  return {
    ...actual,
    api: {
      people: { list: vi.fn(), create: vi.fn() },
      calculations: { create: vi.fn() },
    },
  };
});

function existingPerson(): PersonOut {
  return {
    id: "p1",
    birth_first_names: "Lukas",
    birth_middle_names: null,
    birth_last_name: "Springer",
    birth_date: "1986-07-18",
    birth_time: null,
    birth_place: null,
    current_first_names: null,
    current_middle_names: null,
    current_last_name: null,
    preferred_name: null,
    created_at: "2026-08-19T09:00:00Z",
    updated_at: "2026-08-19T09:00:00Z",
  } as PersonOut;
}

function authenticated() {
  vi.mocked(useAuth).mockReturnValue({
    status: "authenticated",
    user: { id: "u1", email: "ada@example.com", role: "USER", is_active: true },
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
      <OnboardingPage />
    </LocaleProvider>,
  );
}

describe("Onboarding page", () => {
  it("offers 'Zur Übersicht' instead of forcing a new profile when one already exists", async () => {
    vi.mocked(api.people.list).mockResolvedValue([existingPerson()]);
    authenticated();
    renderPage();

    expect(await screen.findByText("Du bist startklar")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Zur Übersicht/ })).toBeInTheDocument();
    expect(screen.queryByLabelText("Vorname(n) *")).not.toBeInTheDocument();
    expect(api.people.create).not.toHaveBeenCalled();
  });

  it("starts the welcome step for an account with no people yet", async () => {
    vi.mocked(api.people.list).mockResolvedValue([]);
    authenticated();
    renderPage();

    expect(await screen.findByText("Willkommen bei Numra")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Erstes Profil anlegen" })).toBeInTheDocument();
  });
});
