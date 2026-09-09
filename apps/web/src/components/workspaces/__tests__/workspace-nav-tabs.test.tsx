import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { WorkspaceNavTabs } from "@/components/workspaces/workspace-nav-tabs";
import { LocaleProvider } from "@/i18n/context";

const usePathname = vi.fn();
vi.mock("next/navigation", () => ({ usePathname: () => usePathname() }));

function renderTabs() {
  return render(
    <LocaleProvider>
      <WorkspaceNavTabs workspaceId="ws-1" />
    </LocaleProvider>,
  );
}

describe("WorkspaceNavTabs", () => {
  it("marks the Overview tab active on the hub route", () => {
    usePathname.mockReturnValue("/workspaces/ws-1");
    renderTabs();
    expect(screen.getByRole("link", { name: "Übersicht" })).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("link", { name: "Freigaben" })).not.toHaveAttribute("aria-current");
  });

  it("marks the Consent tab active on the consent route", () => {
    usePathname.mockReturnValue("/workspaces/ws-1/consent");
    renderTabs();
    expect(screen.getByRole("link", { name: "Freigaben" })).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("link", { name: "Übersicht" })).not.toHaveAttribute("aria-current");
  });

  it("points both tabs at the given workspace id", () => {
    usePathname.mockReturnValue("/workspaces/ws-1");
    renderTabs();
    expect(screen.getByRole("link", { name: "Übersicht" })).toHaveAttribute("href", "/workspaces/ws-1");
    expect(screen.getByRole("link", { name: "Freigaben" })).toHaveAttribute("href", "/workspaces/ws-1/consent");
  });
});
