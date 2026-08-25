import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import AdminUserDetailPage from "@/app/admin/users/[id]/page";
import { api, type AdminUserOut } from "@/api/client";
import { LocaleProvider } from "@/i18n/context";
import { useAuth } from "@/lib/auth-context";

vi.mock("next/navigation", () => ({
  useParams: () => ({ id: "u1" }),
  useRouter: () => ({ replace: vi.fn(), push: vi.fn() }),
  usePathname: () => "/admin/users/u1",
}));

vi.mock("@/lib/auth-context", () => ({ useAuth: vi.fn() }));

vi.mock("@/api/client", async () => {
  const actual = await vi.importActual<typeof import("@/api/client")>("@/api/client");
  return {
    ...actual,
    api: {
      admin: {
        users: {
          get: vi.fn(),
          disable: vi.fn(),
          enable: vi.fn(),
          revokeSessions: vi.fn(),
        },
      },
    },
  };
});

const target: AdminUserOut = {
  id: "u1",
  email: "ada@example.com",
  role: "USER",
  is_active: true,
  created_at: "2026-01-02T10:00:00Z",
  last_login_at: null,
  active_session_count: 1,
  people_count: 0,
  calculation_count: 0,
  report_count: 0,
  relationship_count: 0,
};

function signedInAs(id: string) {
  vi.mocked(useAuth).mockReturnValue({
    status: "authenticated",
    user: { id, email: "admin@example.com", role: "ADMIN", is_active: true },
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
      <AdminUserDetailPage />
    </LocaleProvider>,
  );
}

describe("Admin user detail", () => {
  beforeEach(() => {
    vi.mocked(api.admin.users.get).mockReset().mockResolvedValue(target);
    vi.mocked(api.admin.users.disable).mockReset().mockResolvedValue(undefined);
  });

  it("disables the disable action on the admin's own account and explains why", async () => {
    signedInAs("u1");
    renderPage();

    const button = await screen.findByRole("button", { name: "Konto deaktivieren" });
    expect(button).toBeDisabled();
    expect(
      screen.getByText(/Das eigene Konto kann nicht deaktiviert werden/),
    ).toBeInTheDocument();
  });

  it("calls the disable endpoint only after the confirmation dialog is confirmed", async () => {
    signedInAs("someone-else");
    renderPage();

    fireEvent.click(await screen.findByRole("button", { name: "Konto deaktivieren" }));

    const dialog = screen.getByRole("dialog");
    expect(dialog).toHaveAttribute("aria-modal", "true");
    expect(within(dialog).getByText("Konto deaktivieren?")).toBeInTheDocument();
    expect(api.admin.users.disable).not.toHaveBeenCalled();

    fireEvent.click(within(dialog).getByRole("button", { name: "Konto deaktivieren" }));

    await waitFor(() => expect(api.admin.users.disable).toHaveBeenCalledWith("u1"));
    expect(await screen.findByText("Das Konto wurde deaktiviert.")).toBeInTheDocument();
    // The record is re-read so the view can never show a stale status.
    await waitFor(() => expect(api.admin.users.get).toHaveBeenCalledTimes(2));
  });

  it("closes the dialog on Escape without calling the API", async () => {
    signedInAs("someone-else");
    renderPage();

    fireEvent.click(await screen.findByRole("button", { name: "Konto deaktivieren" }));
    fireEvent.keyDown(screen.getByRole("dialog"), { key: "Escape" });

    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(api.admin.users.disable).not.toHaveBeenCalled();
  });
});
