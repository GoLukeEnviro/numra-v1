import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import AdminFlagsPage from "@/app/admin/flags/page";
import { api, type FeatureFlagOut } from "@/api/client";
import { LocaleProvider } from "@/i18n/context";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  usePathname: () => "/admin/flags",
}));

vi.mock("@/api/client", async () => {
  const actual = await vi.importActual<typeof import("@/api/client")>("@/api/client");
  return {
    ...actual,
    api: {
      ...actual.api,
      admin: {
        ...actual.api.admin,
        flags: {
          list: vi.fn(),
          update: vi.fn(),
        },
      },
    },
  };
});

function flag(overrides: Partial<FeatureFlagOut> = {}): FeatureFlagOut {
  return {
    name: "checkins",
    enabled: false,
    updated_at: "2026-10-01T10:00:00Z",
    updated_by_user_id: null,
    ...overrides,
  };
}

function renderPage() {
  return render(
    <LocaleProvider>
      <AdminFlagsPage />
    </LocaleProvider>,
  );
}

beforeEach(() => {
  vi.mocked(api.admin.flags.list).mockReset();
  vi.mocked(api.admin.flags.update).mockReset();
});

describe("AdminFlagsPage", () => {
  it("lists all flags with their current state", async () => {
    vi.mocked(api.admin.flags.list).mockResolvedValue({
      flags: [flag({ name: "checkins", enabled: false }), flag({ name: "copilot", enabled: true })],
    });
    renderPage();

    expect(await screen.findByRole("switch", { name: /Check-ins/i })).toHaveAttribute(
      "aria-checked",
      "false",
    );
    expect(screen.getByRole("switch", { name: /Copilot/i })).toHaveAttribute("aria-checked", "true");
  });

  it("toggles a flag on and calls the API with the correct arguments", async () => {
    vi.mocked(api.admin.flags.list)
      .mockResolvedValueOnce({ flags: [flag({ name: "checkins", enabled: false })] })
      .mockResolvedValueOnce({ flags: [flag({ name: "checkins", enabled: true })] });
    vi.mocked(api.admin.flags.update).mockResolvedValue(undefined);
    renderPage();

    fireEvent.click(await screen.findByRole("switch", { name: /Check-ins/i }));

    await waitFor(() =>
      expect(screen.getByRole("switch", { name: /Check-ins/i })).toHaveAttribute("aria-checked", "true"),
    );
    expect(await screen.findByRole("switch", { name: /Check-ins/i })).toHaveAttribute(
      "aria-checked",
      "true",
    );
    expect(api.admin.flags.update).toHaveBeenCalledWith("checkins", { enabled: true });
  });

  it("does not flip the switch when the update call fails", async () => {
    vi.mocked(api.admin.flags.list).mockResolvedValue({
      flags: [flag({ name: "checkins", enabled: false })],
    });
    vi.mocked(api.admin.flags.update).mockRejectedValue(new Error("boom"));
    renderPage();

    fireEvent.click(await screen.findByRole("switch", { name: /Check-ins/i }));

    expect(await screen.findByText("Die Änderung konnte nicht gespeichert werden.")).toBeInTheDocument();
    expect(screen.getByRole("switch", { name: /Check-ins/i })).toHaveAttribute("aria-checked", "false");
  });

  it("shows 'last changed' from the server state after a toggle without reload", async () => {
    vi.mocked(api.admin.flags.list)
      .mockResolvedValueOnce({ flags: [flag({ name: "checkins", enabled: false })] })
      .mockResolvedValueOnce({
        flags: [flag({ name: "checkins", enabled: true, updated_by_user_id: "admin-1" })],
      });
    vi.mocked(api.admin.flags.update).mockResolvedValue(undefined);
    renderPage();

    expect(await screen.findByText(/Noch nie geändert/)).toBeInTheDocument();
    fireEvent.click(await screen.findByRole("switch", { name: /Check-ins/i }));

    await waitFor(() => expect(screen.queryByText(/Noch nie geändert/)).not.toBeInTheDocument());
    expect(screen.getByRole("switch", { name: /Check-ins/i })).toHaveAttribute("aria-checked", "true");
  });
});
