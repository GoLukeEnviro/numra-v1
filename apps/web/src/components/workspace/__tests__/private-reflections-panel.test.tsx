import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { PrivateReflectionsPanel } from "@/components/workspace/private-reflections-panel";
import { api, type PrivateReflectionOut } from "@/api/client";
import { LocaleProvider } from "@/i18n/context";

vi.mock("@/api/client", async () => {
  const actual = await vi.importActual<typeof import("@/api/client")>("@/api/client");
  return {
    ...actual,
    api: {
      people: {
        privateReflections: {
          list: vi.fn(),
          create: vi.fn(),
          patch: vi.fn(),
          remove: vi.fn(),
        },
      },
    },
  };
});

const PERSON_A = "person-a";

function entry(overrides: Partial<PrivateReflectionOut> = {}): PrivateReflectionOut {
  return {
    id: "reflection-1",
    person_id: PERSON_A,
    entry_date: "2026-03-01",
    content: "A quiet, reflective day.",
    created_at: "2026-03-01T00:00:00Z",
    updated_at: "2026-03-01T00:00:00Z",
    ...overrides,
  };
}

function renderPanel(personId = PERSON_A, managedProfile = false) {
  return render(
    <LocaleProvider>
      <PrivateReflectionsPanel personId={personId} managedProfile={managedProfile} />
    </LocaleProvider>,
  );
}

describe("PrivateReflectionsPanel", () => {
  beforeEach(() => {
    vi.mocked(api.people.privateReflections.list).mockReset();
    vi.mocked(api.people.privateReflections.create).mockReset();
    vi.mocked(api.people.privateReflections.patch).mockReset();
    vi.mocked(api.people.privateReflections.remove).mockReset();
  });

  it("shows a loading state while the list request is in flight", () => {
    vi.mocked(api.people.privateReflections.list).mockReturnValue(new Promise(() => {}));
    renderPanel();
    expect(screen.getByRole("status")).toBeInTheDocument();
  });

  it("shows an error state with retry on failure", async () => {
    vi.mocked(api.people.privateReflections.list).mockRejectedValue(new Error("boom"));
    renderPanel();
    expect(await screen.findByRole("alert")).toHaveTextContent("boom");
  });

  it("shows the empty state with a create CTA", async () => {
    vi.mocked(api.people.privateReflections.list).mockResolvedValue([]);
    renderPanel();
    expect(await screen.findByText("Noch keine Reflexionen")).toBeInTheDocument();
  });

  it("renders entries sorted by entry_date desc", async () => {
    vi.mocked(api.people.privateReflections.list).mockResolvedValue([
      entry({ id: "old", entry_date: "2026-01-01" }),
      entry({ id: "new", entry_date: "2026-02-01" }),
    ]);
    renderPanel();

    const items = await screen.findAllByRole("listitem");
    expect(items[0]).toHaveTextContent("01.02.2026");
    expect(items[1]).toHaveTextContent("01.01.2026");
  });

  it("creates an entry via the inline form, defaulting the date to today", async () => {
    vi.mocked(api.people.privateReflections.list).mockResolvedValueOnce([]).mockResolvedValueOnce([entry()]);
    vi.mocked(api.people.privateReflections.create).mockResolvedValue(entry());
    renderPanel();

    await screen.findByText("Noch keine Reflexionen");
    fireEvent.click(screen.getByRole("button", { name: /Ersten Eintrag erstellen/ }));
    fireEvent.change(screen.getByLabelText("Inhalt"), { target: { value: "A quiet, reflective day." } });
    fireEvent.click(screen.getByRole("button", { name: "Speichern" }));

    await waitFor(() => expect(api.people.privateReflections.create).toHaveBeenCalled());
    await waitFor(() => expect(api.people.privateReflections.list).toHaveBeenCalledTimes(2));
    await waitFor(() => expect(screen.getByText("A quiet, reflective day.")).toBeInTheDocument());
    expect(api.people.privateReflections.create).toHaveBeenCalledWith(
      PERSON_A,
      expect.objectContaining({ content: "A quiet, reflective day." }),
    );
  });

  it("has no share button anywhere in the panel", async () => {
    vi.mocked(api.people.privateReflections.list).mockResolvedValue([entry()]);
    renderPanel();
    await screen.findByText("A quiet, reflective day.");
    expect(screen.queryByRole("button", { name: /share/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /teilen/i })).not.toBeInTheDocument();
  });

  it("requires a two-step inline confirmation before deleting", async () => {
    vi.mocked(api.people.privateReflections.list).mockResolvedValue([entry()]);
    renderPanel();
    const item = (await screen.findByText("A quiet, reflective day.")).closest("li")!;

    fireEvent.click(within(item).getByRole("button", { name: "Löschen" }));
    expect(api.people.privateReflections.remove).not.toHaveBeenCalled();
    fireEvent.click(within(item).getByRole("button", { name: "Endgültig löschen" }));
    expect(api.people.privateReflections.remove).toHaveBeenCalledWith("reflection-1");
  });
});
