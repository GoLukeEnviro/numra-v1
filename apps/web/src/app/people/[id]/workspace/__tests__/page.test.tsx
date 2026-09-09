import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import WorkspaceHubPage from "@/app/people/[id]/workspace/page";
import { api, type MyWorkspaceOverviewOut, type PersonOut } from "@/api/client";
import { LocaleProvider } from "@/i18n/context";
import { useAuth } from "@/lib/auth-context";

vi.mock("next/navigation", () => ({
  useParams: () => ({ id: "person-a" }),
  useRouter: () => ({ replace: vi.fn(), push: vi.fn() }),
  usePathname: () => "/people/person-a/workspace",
}));

vi.mock("@/lib/auth-context", () => ({ useAuth: vi.fn() }));

vi.mock("@/api/client", async () => {
  const actual = await vi.importActual<typeof import("@/api/client")>("@/api/client");
  return {
    ...actual,
    api: {
      myWorkspace: { get: vi.fn() },
      people: {
        list: vi.fn(),
        privateNotes: { list: vi.fn() },
        privateReflections: { list: vi.fn() },
      },
      personalTasks: { list: vi.fn() },
    },
  };
});

const PERSON: PersonOut = {
  id: "person-a",
  birth_date: "1990-05-14",
  birth_first_names: "Ada",
  birth_last_name: "Lovelace",
  birth_middle_names: null,
  birth_place: null,
  birth_time: null,
  created_at: "2026-01-01T00:00:00Z",
  current_first_names: null,
  current_last_name: null,
  current_middle_names: null,
  person_account_mode: "SELF",
  preferred_name: null,
  updated_at: "2026-01-01T00:00:00Z",
};

const OVERVIEW: MyWorkspaceOverviewOut = {
  person: PERSON,
  latest_calculation: {
    id: "calc-1",
    person_id: "person-a",
    as_of_date: "2026-01-01",
    calculation_version: "1",
    schema_version: "1",
    deterministic_hash: "abcdef123456",
    created_at: "2026-01-01T00:00:00Z",
  },
  reports: { total: 2, latest: null },
  private_reflections: { total: 1, latest: null },
  private_notes: { total: 3 },
  personal_tasks: { total: 5, active: 3 },
};

function signedIn() {
  vi.mocked(useAuth).mockReturnValue({
    status: "authenticated",
    user: { id: "u1", email: "ada@example.com", role: "USER", is_active: true },
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
      <WorkspaceHubPage />
    </LocaleProvider>,
  );
}

describe("WorkspaceHubPage", () => {
  beforeEach(() => {
    signedIn();
    vi.mocked(api.myWorkspace.get).mockReset();
    vi.mocked(api.people.list).mockReset();
    vi.mocked(api.people.privateNotes.list).mockReset().mockResolvedValue([]);
    vi.mocked(api.people.privateReflections.list).mockReset().mockResolvedValue([]);
    vi.mocked(api.personalTasks.list).mockReset().mockResolvedValue([]);
  });

  it("shows a loading state while the overview request is in flight", () => {
    vi.mocked(api.myWorkspace.get).mockReturnValue(new Promise(() => {}));
    vi.mocked(api.people.list).mockReturnValue(new Promise(() => {}));
    renderPage();
    expect(screen.getByText("Workspace wird geladen…")).toBeInTheDocument();
  });

  it("shows an error state with retry when the overview request fails", async () => {
    vi.mocked(api.myWorkspace.get).mockRejectedValue(new Error("boom"));
    vi.mocked(api.people.list).mockResolvedValue([PERSON]);
    renderPage();
    expect(await screen.findByRole("alert")).toHaveTextContent("boom");
  });

  it("renders the five clusters with real overview data once loaded", async () => {
    vi.mocked(api.myWorkspace.get).mockResolvedValue(OVERVIEW);
    vi.mocked(api.people.list).mockResolvedValue([PERSON]);
    renderPage();

    expect(await screen.findByText("Ada Lovelace")).toBeInTheDocument();
    expect(screen.getByText("PROFIL")).toBeInTheDocument();
    expect(screen.getByText("MUSTER")).toBeInTheDocument();
    expect(screen.getByText("AKTUELL")).toBeInTheDocument();
    expect(screen.getByText("ARBEITEN")).toBeInTheDocument();
    expect(screen.getByText("ARCHIV")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Profilanalyse öffnen/ })).toHaveAttribute(
      "href",
      "/analysis/calc-1",
    );
    expect(screen.getByText(/2 Berichte insgesamt/)).toBeInTheDocument();
  });
});
