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
  it("renders the five workspace tabs", () => {
    usePathname.mockReturnValue("/workspaces/ws-1");
    renderTabs();
    expect(screen.getAllByRole("link")).toHaveLength(5);
    expect(screen.getByRole("link", { name: "Dynamiken" })).toHaveAttribute(
      "href",
      "/workspaces/ws-1/dynamics",
    );
  });

  it("marks the Tasks tab active on the tasks route", () => {
    usePathname.mockReturnValue("/workspaces/ws-1/tasks");
    renderTabs();
    expect(screen.getByRole("link", { name: "Aufgaben" })).toHaveAttribute("aria-current", "page");
  });

  it("marks the Check-ins tab active on the check-ins route", () => {
    usePathname.mockReturnValue("/workspaces/ws-1/checkins");
    renderTabs();
    expect(screen.getByRole("link", { name: "Check-ins" })).toHaveAttribute("aria-current", "page");
  });

  it("marks the Dynamics tab active on the dynamics route", () => {
    usePathname.mockReturnValue("/workspaces/ws-1/dynamics");
    renderTabs();
    expect(screen.getByRole("link", { name: "Dynamiken" })).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("link", { name: "Übersicht" })).not.toHaveAttribute("aria-current");
  });

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
