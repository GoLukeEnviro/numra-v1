import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import AdminDashboardPage from "@/app/admin/page";
import { api, type AdminStatsOut } from "@/api/client";
import { LocaleProvider } from "@/i18n/context";

vi.mock("@/api/client", async () => {
  const actual = await vi.importActual<typeof import("@/api/client")>("@/api/client");
  return { ...actual, api: { admin: { stats: vi.fn() } } };
});

const stats: AdminStatsOut = {
  total_users: 42,
  active_users: 40,
  disabled_users: 2,
  registrations_last_7_days: 5,
  registrations_last_30_days: 17,
  active_sessions: 11,
  total_people: 130,
  total_calculations: 260,
  total_reports: 8,
};

function renderPage() {
  return render(
    <LocaleProvider>
      <AdminDashboardPage />
    </LocaleProvider>,
  );
}

describe("Admin dashboard", () => {
  beforeEach(() => {
    vi.mocked(api.admin.stats).mockReset();
  });

  it("renders every stat the endpoint returned", async () => {
    vi.mocked(api.admin.stats).mockResolvedValue(stats);
    renderPage();

    expect(await screen.findByText("42")).toBeInTheDocument();
    expect(screen.getByText("Benutzer gesamt")).toBeInTheDocument();
    expect(screen.getByText("Registrierungen letzte 7 Tage")).toBeInTheDocument();
    expect(screen.getByText("5")).toBeInTheDocument();
    expect(screen.getByText("Aktive Sessions")).toBeInTheDocument();
    expect(screen.getByText("11")).toBeInTheDocument();
    expect(screen.getByText("260")).toBeInTheDocument();
  });

  it("shows an error state when the request fails", async () => {
    vi.mocked(api.admin.stats).mockRejectedValue(new Error("boom"));
    renderPage();

    expect(await screen.findByRole("alert")).toHaveTextContent("boom");
    expect(screen.queryByText("Benutzer gesamt")).not.toBeInTheDocument();
  });
});
