import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ConsentBadge, ConsentList, type ConsentListEntry } from "@/components/consent/consent-badge";
import { LocaleProvider } from "@/i18n/context";
import { WorkspaceSwitcher, type WorkspaceOption } from "@/components/workspaces/workspace-switcher";

describe("ConsentBadge", () => {
  it("renders GRANTED with the success variant", () => {
    render(<ConsentBadge status="GRANTED" />);
    const badge = screen.getByText("GRANTED");
    expect(badge.className).toMatch(/text-success/);
  });

  it("renders PENDING with the neutral variant", () => {
    render(<ConsentBadge status="PENDING" />);
    const badge = screen.getByText("PENDING");
    expect(badge.className).toMatch(/text-muted/);
  });

  it("renders REVOKED with the muted diagnostic variant, not danger", () => {
    render(<ConsentBadge status="REVOKED" />);
    const badge = screen.getByText("REVOKED");
    expect(badge.className).toMatch(/border-dashed/);
    expect(badge.className).not.toMatch(/danger/);
  });
});

// Replaces the removed /dev/pr-web-00-demo Playwright screenshot (g): ConsentBadge's
// 3 status variants side by side, ConsentList, and WorkspaceSwitcher rendered
// together as they were in that demo, without any Playwright/screenshot mechanism.
describe("ConsentBadge/ConsentList + WorkspaceSwitcher combined demo coverage", () => {
  const CONSENT_ENTRIES: ConsentListEntry[] = [
    { id: "c1", participantName: "Mira Vance", status: "GRANTED" },
    { id: "c2", participantName: "Jonas Keller", status: "PENDING" },
    { id: "c3", participantName: "Alex Rohde", status: "REVOKED" },
  ];

  const WORKSPACE_OPTIONS: WorkspaceOption[] = [
    { id: "ws-1", label: "Lukas", kind: "PERSONAL" },
    { id: "ws-2", label: "Lukas & Mira", kind: "RELATIONSHIP" },
  ];

  it("renders the 3 ConsentBadge variants, a ConsentList, and the WorkspaceSwitcher together", () => {
    render(
      <LocaleProvider>
        <div>
          <ConsentBadge status="GRANTED" />
          <ConsentBadge status="PENDING" />
          <ConsentBadge status="REVOKED" />
        </div>
        <ConsentList entries={CONSENT_ENTRIES} />
        <WorkspaceSwitcher options={WORKSPACE_OPTIONS} activeId="ws-1" onSelect={() => {}} />
      </LocaleProvider>,
    );

    expect(screen.getAllByText("GRANTED")).toHaveLength(2); // standalone badge + ConsentList row
    expect(screen.getAllByText("PENDING")).toHaveLength(2);
    expect(screen.getAllByText("REVOKED")).toHaveLength(2);
    expect(screen.getByText("Mira Vance")).toBeInTheDocument();
    expect(screen.getByText("Jonas Keller")).toBeInTheDocument();
    expect(screen.getByText("Alex Rohde")).toBeInTheDocument();
    expect(screen.getByRole("combobox", { name: "Workspace wechseln" })).toBeInTheDocument();
  });
});
