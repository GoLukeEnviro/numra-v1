import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { AppShell } from "@/components/layout/app-shell";
import { LocaleProvider } from "@/i18n/context";
import { useAuth } from "@/lib/auth-context";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: vi.fn(), push: vi.fn() }),
  usePathname: () => "/dashboard",
}));

vi.mock("@/lib/auth-context", () => ({ useAuth: vi.fn() }));

function signedInAs(role: "USER" | "ADMIN") {
  vi.mocked(useAuth).mockReturnValue({
    status: "authenticated",
    user: { id: "u1", email: "someone@example.com", role, is_active: true },
    error: null,
    login: vi.fn(),
    register: vi.fn(),
    logout: vi.fn(),
    refresh: vi.fn(),
  } as ReturnType<typeof useAuth>);
}

function renderShell() {
  return render(
    <LocaleProvider>
      <AppShell>
        <p>Seiteninhalt</p>
      </AppShell>
    </LocaleProvider>,
  );
}

describe("role-aware app navigation", () => {
  it("offers the admin entry in the sidebar and the mobile sheet for an ADMIN", () => {
    signedInAs("ADMIN");
    renderShell();

    expect(screen.getAllByRole("link", { name: "Admin" }).length).toBe(1);

    fireEvent.click(screen.getByRole("button", { name: /Mehr/ }));
    expect(screen.getAllByRole("link", { name: "Admin" }).length).toBe(2);
  });

  it("does not put the admin entry in a USER's markup at all", () => {
    signedInAs("USER");
    renderShell();

    expect(screen.queryByRole("link", { name: "Admin" })).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /Mehr/ }));
    expect(screen.queryByRole("link", { name: "Admin" })).not.toBeInTheDocument();
  });
});
