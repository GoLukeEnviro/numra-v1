import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { DualProfileGrid } from "@/components/workspaces/dual-profile-grid";
import { LocaleProvider } from "@/i18n/context";
import { useAuth } from "@/lib/auth-context";
import type { DualProfileMemberOut } from "@/api/client";

vi.mock("@/lib/auth-context", () => ({ useAuth: vi.fn() }));

function signedIn(userId: string) {
  vi.mocked(useAuth).mockReturnValue({
    status: "authenticated",
    user: { id: userId, email: "me@example.com", role: "USER", is_active: true },
    error: null,
    login: vi.fn(),
    register: vi.fn(),
    logout: vi.fn(),
    refresh: vi.fn(),
  } as ReturnType<typeof useAuth>);
}

function selfMember(overrides: Partial<DualProfileMemberOut> = {}): DualProfileMemberOut {
  return {
    user_id: "me",
    display_name: "Lukas Springer",
    self_person: { id: "p1", display_name: "Lukas Springer" },
    core_numbers: {
      life_path: { display_value: "8" },
      expression: { display_value: "3" },
    },
    ...overrides,
  } as DualProfileMemberOut;
}

function counterpartMember(overrides: Partial<DualProfileMemberOut> = {}): DualProfileMemberOut {
  return {
    user_id: "them",
    display_name: "Ada Lovelace",
    self_person: null,
    core_numbers: null,
    ...overrides,
  } as DualProfileMemberOut;
}

beforeEach(() => {
  signedIn("me");
});

function renderGrid(members: DualProfileMemberOut[]) {
  return render(
    <LocaleProvider>
      <DualProfileGrid workspaceId="ws-1" members={members} />
    </LocaleProvider>,
  );
}

describe("DualProfileGrid", () => {
  it("renders the own side's core numbers by display_value", () => {
    renderGrid([selfMember(), counterpartMember()]);
    expect(screen.getByText("8")).toBeInTheDocument();
    expect(screen.getByText("3")).toBeInTheDocument();
  });

  it("degrades gracefully with a calm hint when the counterpart has no consent, no crash and no danger styling", () => {
    renderGrid([selfMember(), counterpartMember()]);
    expect(screen.getByText(/hat die Kernzahlen noch nicht freigegeben\./)).toBeInTheDocument();
    expect(screen.getAllByText("Ada Lovelace").length).toBeGreaterThan(0);
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Freigaben ansehen" })).toHaveAttribute(
      "href",
      "/workspaces/ws-1/consent",
    );
  });

  it("renders full counterpart core numbers when consent has been granted", () => {
    renderGrid([
      selfMember(),
      counterpartMember({
        self_person: { id: "p2", display_name: "Ada Lovelace" },
        core_numbers: { life_path: { display_value: "1" } },
      }),
    ]);
    expect(screen.getByText("1")).toBeInTheDocument();
  });

  it("skips unknown or malformed core-number keys without crashing", () => {
    renderGrid([
      selfMember({
        core_numbers: {
          life_path: { display_value: "8" },
          unknown_metric: { display_value: "99" },
          expression: "not-an-object",
          maturity: null,
        },
      }),
      counterpartMember(),
    ]);
    expect(screen.getByText("8")).toBeInTheDocument();
    expect(screen.queryByText("99")).not.toBeInTheDocument();
  });

  it("marks the SharedBadge shown for the counterpart card", () => {
    renderGrid([selfMember(), counterpartMember()]);
    expect(screen.getByText("Geteilt")).toBeInTheDocument();
  });
});
