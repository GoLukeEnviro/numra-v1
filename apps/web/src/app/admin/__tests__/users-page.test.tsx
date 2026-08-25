import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import AdminUsersPage from "@/app/admin/users/page";
import { api, type AdminUserListOut, type AdminUserOut } from "@/api/client";
import { LocaleProvider } from "@/i18n/context";

vi.mock("@/api/client", async () => {
  const actual = await vi.importActual<typeof import("@/api/client")>("@/api/client");
  return { ...actual, api: { admin: { users: { list: vi.fn() } } } };
});

function user(overrides: Partial<AdminUserOut> = {}): AdminUserOut {
  return {
    id: "u1",
    email: "ada@example.com",
    role: "USER",
    is_active: true,
    created_at: "2026-01-02T10:00:00Z",
    last_login_at: null,
    active_session_count: 1,
    people_count: 2,
    calculation_count: 3,
    report_count: 4,
    relationship_count: 5,
    ...overrides,
  };
}

const listPage: AdminUserListOut = {
  items: [user(), user({ id: "u2", email: "grace@example.com", role: "ADMIN" })],
  total: 30,
  page: 1,
  page_size: 25,
};

function renderPage() {
  return render(
    <LocaleProvider>
      <AdminUsersPage />
    </LocaleProvider>,
  );
}

describe("Admin user list", () => {
  beforeEach(() => {
    vi.mocked(api.admin.users.list).mockReset();
    vi.mocked(api.admin.users.list).mockResolvedValue(listPage);
  });

  it("renders one entry per returned user", async () => {
    renderPage();
    // Rendered twice by design: a card list for phones, a table from md up.
    expect((await screen.findAllByText("ada@example.com")).length).toBeGreaterThan(0);
    expect(screen.getAllByText("grace@example.com").length).toBeGreaterThan(0);
    // 30 results at 25 per page — the page count comes from the server's own totals.
    expect(screen.getByText("Seite 1 / 2")).toBeInTheDocument();
  });

  it("re-queries the server with the role filter instead of filtering locally", async () => {
    renderPage();
    await screen.findAllByText("ada@example.com");

    fireEvent.change(screen.getByLabelText("Rolle"), { target: { value: "ADMIN" } });

    await waitFor(() => {
      expect(api.admin.users.list).toHaveBeenLastCalledWith(
        expect.objectContaining({ role: "ADMIN", page: 1, pageSize: 25 }),
      );
    });
  });

  it("passes the search term to the server on submit", async () => {
    renderPage();
    await screen.findAllByText("ada@example.com");

    fireEvent.change(screen.getByLabelText("Suche nach E-Mail"), {
      target: { value: " ada@example.com " },
    });
    fireEvent.click(screen.getByRole("button", { name: "Suchen" }));

    await waitFor(() => {
      expect(api.admin.users.list).toHaveBeenLastCalledWith(
        expect.objectContaining({ search: "ada@example.com", page: 1 }),
      );
    });
  });

  it("requests the next page when paginating", async () => {
    renderPage();
    await screen.findAllByText("ada@example.com");

    fireEvent.click(screen.getByRole("button", { name: "Weiter" }));

    await waitFor(() => {
      expect(api.admin.users.list).toHaveBeenLastCalledWith(
        expect.objectContaining({ page: 2, pageSize: 25 }),
      );
    });
  });
});
