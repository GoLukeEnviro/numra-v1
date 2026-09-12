import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import EvidencePage from "@/app/people/[id]/evidence/page";
import { api } from "@/api/client";
import { LocaleProvider } from "@/i18n/context";
import { useAuth } from "@/lib/auth-context";

vi.mock("next/navigation", () => ({
  useParams: () => ({ id: "person-1" }),
  usePathname: () => "/people/person-1/evidence",
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
}));
vi.mock("@/lib/auth-context", () => ({ useAuth: vi.fn() }));
vi.mock("@/api/client", async () => {
  const actual = await vi.importActual<typeof import("@/api/client")>("@/api/client");
  return { ...actual, api: {
    ...actual.api,
    people: { ...actual.api.people, get: vi.fn(), lifeTracking: { list: vi.fn(), create: vi.fn(), remove: vi.fn() } },
    evidence: { result: vi.fn(), analyses: { list: vi.fn(), create: vi.fn(), remove: vi.fn() } },
  } };
});

describe("EvidencePage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(useAuth).mockReturnValue({ status: "authenticated", user: { id: "user-1" }, error: null } as ReturnType<typeof useAuth>);
    vi.mocked(api.people.get).mockResolvedValue({
      id: "person-1", person_account_mode: "SELF", birth_first_names: "Lukas", birth_middle_names: null, birth_last_name: "Beispiel",
      birth_date: "1990-03-14", birth_time: null, birth_place: null, preferred_name: null,
      current_first_names: null, current_middle_names: null, current_last_name: null,
      created_at: "2026-01-01T00:00:00Z", updated_at: "2026-01-01T00:00:00Z",
    });
    vi.mocked(api.people.lifeTracking.list).mockResolvedValue([]);
    vi.mocked(api.evidence.analyses.list).mockResolvedValue([]);
  });

  it("loads the owned person before rendering the evidence surface", async () => {
    render(<LocaleProvider><EvidencePage /></LocaleProvider>);
    expect(await screen.findByRole("heading", { name: "Life Tracking & Evidenz" })).toBeInTheDocument();
    expect(screen.getByText(/für Lukas Beispiel tägliche Beobachtungen/)).toBeInTheDocument();
    expect(api.people.get).toHaveBeenCalledWith("person-1");
  });
});
