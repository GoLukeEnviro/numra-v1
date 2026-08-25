import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import LandingPage from "@/app/page";
import { LocaleProvider } from "@/i18n/context";
import { useAuth } from "@/lib/auth-context";

vi.mock("@/lib/auth-context", () => ({ useAuth: vi.fn() }));

function anonymous() {
  vi.mocked(useAuth).mockReturnValue({
    status: "anonymous",
    user: null,
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
      <LandingPage />
    </LocaleProvider>,
  );
}

describe("Public landing page", () => {
  it("renders publicly for an anonymous visitor without redirecting", () => {
    anonymous();
    renderPage();

    expect(screen.getByRole("heading", { level: 1, name: "Numerologie ohne Raten." })).toBeInTheDocument();
  });

  it("shows both sign-in and create-account CTAs", () => {
    anonymous();
    renderPage();

    expect(screen.getAllByRole("link", { name: "Anmelden" }).length).toBeGreaterThan(0);
    expect(screen.getAllByRole("link", { name: "Konto erstellen" }).length).toBeGreaterThan(0);
  });

  it("includes the numerology disclaimer", () => {
    anonymous();
    renderPage();

    expect(
      screen.getByText(/symbolisches numerologisches Interpretationswerkzeug/),
    ).toBeInTheDocument();
  });

  it("offers a dashboard entry point for an already authenticated visitor without redirecting away", () => {
    vi.mocked(useAuth).mockReturnValue({
      status: "authenticated",
      user: { id: "u1", email: "ada@example.com", role: "USER", is_active: true },
      error: null,
      login: vi.fn(),
      register: vi.fn(),
      logout: vi.fn(),
      refresh: vi.fn(),
    } as ReturnType<typeof useAuth>);
    renderPage();

    expect(screen.getAllByRole("link", { name: "Zur Übersicht" }).length).toBeGreaterThan(0);
    expect(screen.getByRole("heading", { level: 1, name: "Numerologie ohne Raten." })).toBeInTheDocument();
  });
});
