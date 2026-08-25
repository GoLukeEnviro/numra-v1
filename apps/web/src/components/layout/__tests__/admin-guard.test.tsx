import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AdminGuard } from "@/components/layout/admin-guard";
import { LocaleProvider } from "@/i18n/context";
import { useAuth } from "@/lib/auth-context";

const replace = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace, push: vi.fn() }),
  usePathname: () => "/admin",
}));

vi.mock("@/lib/auth-context", () => ({ useAuth: vi.fn() }));

const mockedUseAuth = vi.mocked(useAuth);

function renderGuard() {
  return render(
    <LocaleProvider>
      <AdminGuard>
        <p>Streng vertraulicher Admin-Inhalt</p>
      </AdminGuard>
    </LocaleProvider>,
  );
}

function authState(overrides: Partial<ReturnType<typeof useAuth>>) {
  return {
    status: "authenticated",
    user: null,
    error: null,
    login: vi.fn(),
    logout: vi.fn(),
    refresh: vi.fn(),
    ...overrides,
  } as ReturnType<typeof useAuth>;
}

describe("AdminGuard", () => {
  beforeEach(() => {
    replace.mockClear();
  });

  it("renders no admin content for an anonymous visitor and sends them to the admin login", () => {
    mockedUseAuth.mockReturnValue(authState({ status: "anonymous" }));
    renderGuard();

    expect(screen.queryByText("Streng vertraulicher Admin-Inhalt")).not.toBeInTheDocument();
    expect(replace).toHaveBeenCalledWith("/admin/login");
  });

  it("shows access denied and no admin content for a signed-in USER", () => {
    mockedUseAuth.mockReturnValue(
      authState({ user: { id: "u1", email: "u@example.com", role: "USER", is_active: true } }),
    );
    renderGuard();

    expect(screen.getByText("Kein Zugriff")).toBeInTheDocument();
    expect(screen.queryByText("Streng vertraulicher Admin-Inhalt")).not.toBeInTheDocument();
    expect(replace).not.toHaveBeenCalled();
  });

  it("renders the content for an ADMIN", () => {
    mockedUseAuth.mockReturnValue(
      authState({ user: { id: "a1", email: "a@example.com", role: "ADMIN", is_active: true } }),
    );
    renderGuard();

    expect(screen.getByText("Streng vertraulicher Admin-Inhalt")).toBeInTheDocument();
    expect(screen.queryByText("Kein Zugriff")).not.toBeInTheDocument();
  });
});
