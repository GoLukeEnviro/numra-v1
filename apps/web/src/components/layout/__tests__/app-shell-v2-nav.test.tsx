import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { AppShell } from "@/components/layout/app-shell";
import { LocaleProvider } from "@/i18n/context";
import { useAuth } from "@/lib/auth-context";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: vi.fn(), push: vi.fn() }),
  usePathname: () => "/dashboard",
}));

vi.mock("@/lib/auth-context", () => ({ useAuth: vi.fn() }));

function renderShell() {
  vi.mocked(useAuth).mockReturnValue({
    status: "authenticated",
    user: { id: "u1", email: "someone@example.com", role: "USER", is_active: true },
    error: null,
    login: vi.fn(),
    register: vi.fn(),
    logout: vi.fn(),
    refresh: vi.fn(),
  } as ReturnType<typeof useAuth>);

  return render(
    <LocaleProvider>
      <AppShell>
        <p>Seiteninhalt</p>
      </AppShell>
    </LocaleProvider>,
  );
}

/** V2 shell (PR-WEB-00): the three new placeholder nav entries exist with the
 *  correct hrefs, in the correct desktop order. */
describe("V2 shell navigation", () => {
  it("offers Connections, Workspaces and Copilot links with the correct hrefs", () => {
    renderShell();

    expect(screen.getAllByRole("link", { name: "Verbindungen" })[0]).toHaveAttribute(
      "href",
      "/connections",
    );
    expect(screen.getAllByRole("link", { name: "Workspaces" })[0]).toHaveAttribute(
      "href",
      "/workspaces",
    );
    // Copilot only appears once: it's a desktop-nav / mobile-"More" item, not one
    // of the four mobile bottom-bar primary slots.
    expect(screen.getByRole("link", { name: "Copilot" })).toHaveAttribute("href", "/copilot");
  });

  it("orders the desktop sidebar as Home, Profile, Connections, Workspaces, Today, Copilot, Settings, then Relationships/Reports", () => {
    renderShell();

    const expectedOrder = [
      "Übersicht",
      "Personen",
      "Verbindungen",
      "Workspaces",
      "Heute",
      "Copilot",
      "Einstellungen",
      "Beziehungen",
      "Berichte",
    ];
    const links = screen.getAllByRole("link").map((el) => el.textContent?.trim());
    const observedOrder = expectedOrder.filter((label) => links.includes(label));
    const indices = observedOrder.map((label) => links.indexOf(label));

    expect(indices).toEqual([...indices].sort((a, b) => a - b));
    expect(observedOrder).toEqual(expectedOrder);
  });
});
