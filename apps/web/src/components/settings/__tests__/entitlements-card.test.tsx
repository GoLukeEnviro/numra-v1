import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { EntitlementsCard } from "@/components/settings/entitlements-card";
import { api, type EntitlementSetOut } from "@/api/client";
import { LocaleProvider } from "@/i18n/context";

vi.mock("@/api/client", async () => {
  const actual = await vi.importActual<typeof import("@/api/client")>("@/api/client");
  return { ...actual, api: { entitlements: { get: vi.fn() } } };
});

const entitlements: EntitlementSetOut = {
  advanced_relationship_analysis: true,
  connections: true,
  life_tracking: false,
  max_connections: 5,
  max_workspaces: null,
  personal_workspace: true,
  premium_reports: false,
  relationship_checkins: true,
  relationship_copilot: false,
  relationship_workspaces: true,
};

function renderCard() {
  return render(
    <LocaleProvider>
      <EntitlementsCard />
    </LocaleProvider>,
  );
}

describe("EntitlementsCard", () => {
  beforeEach(() => {
    vi.mocked(api.entitlements.get).mockReset();
  });

  it("renders all 8 boolean features and both limits read-only", async () => {
    vi.mocked(api.entitlements.get).mockResolvedValue(entitlements);
    renderCard();

    expect(await screen.findByText("Persönlicher Workspace")).toBeInTheDocument();
    expect(screen.getByText("Verbindungen")).toBeInTheDocument();
    expect(screen.getByText("Beziehungs-Workspaces")).toBeInTheDocument();
    expect(screen.getByText("Beziehungs-Check-ins")).toBeInTheDocument();
    expect(screen.getByText("Beziehungs-Copilot")).toBeInTheDocument();
    expect(screen.getByText("Erweiterte Beziehungsanalyse")).toBeInTheDocument();
    expect(screen.getByText("Life Tracking")).toBeInTheDocument();
    expect(screen.getByText("Premium-Berichte")).toBeInTheDocument();

    expect(screen.getByText("5")).toBeInTheDocument();
    expect(screen.getByText("Unbegrenzt")).toBeInTheDocument();

    // Read-only: no button, checkbox, or other interactive control anywhere in the card.
    expect(screen.queryAllByRole("button")).toHaveLength(0);
    expect(screen.queryAllByRole("checkbox")).toHaveLength(0);
  });

  it("shows an error state when the request fails", async () => {
    vi.mocked(api.entitlements.get).mockRejectedValue(new Error("boom"));
    renderCard();

    expect(await screen.findByRole("alert")).toHaveTextContent("boom");
    expect(screen.queryByText("Verbindungen")).not.toBeInTheDocument();
  });
});
