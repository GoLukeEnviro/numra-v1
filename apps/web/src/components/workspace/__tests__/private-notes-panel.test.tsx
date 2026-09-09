import { fireEvent, render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { PrivateNotesPanel } from "@/components/workspace/private-notes-panel";
import { api, type PrivateNoteOut } from "@/api/client";
import { LocaleProvider } from "@/i18n/context";

vi.mock("@/api/client", async () => {
  const actual = await vi.importActual<typeof import("@/api/client")>("@/api/client");
  return {
    ...actual,
    api: {
      people: {
        privateNotes: {
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

function note(overrides: Partial<PrivateNoteOut> = {}): PrivateNoteOut {
  return {
    id: "note-1",
    person_id: PERSON_A,
    title: "First impression",
    content: "Very grounded energy.",
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-02T00:00:00Z",
    ...overrides,
  };
}

function renderPanel(personId = PERSON_A, managedProfile = false) {
  return render(
    <LocaleProvider>
      <PrivateNotesPanel personId={personId} managedProfile={managedProfile} />
    </LocaleProvider>,
  );
}

describe("PrivateNotesPanel", () => {
  beforeEach(() => {
    vi.mocked(api.people.privateNotes.list).mockReset();
    vi.mocked(api.people.privateNotes.create).mockReset();
    vi.mocked(api.people.privateNotes.patch).mockReset();
    vi.mocked(api.people.privateNotes.remove).mockReset();
  });

  it("shows a loading state while the list request is in flight", () => {
    vi.mocked(api.people.privateNotes.list).mockReturnValue(new Promise(() => {}));
    renderPanel();
    expect(screen.getByRole("status")).toBeInTheDocument();
  });

  it("shows an error state with retry on failure", async () => {
    vi.mocked(api.people.privateNotes.list).mockRejectedValue(new Error("boom"));
    renderPanel();
    expect(await screen.findByRole("alert")).toHaveTextContent("boom");
  });

  it("shows the empty state with a create CTA", async () => {
    vi.mocked(api.people.privateNotes.list).mockResolvedValue([]);
    renderPanel();
    expect(await screen.findByText("Noch keine Notizen")).toBeInTheDocument();
  });

  it("renders notes sorted by updated_at desc, with an untitled fallback", async () => {
    vi.mocked(api.people.privateNotes.list).mockResolvedValue([
      note({ id: "old", title: null, updated_at: "2026-01-01T00:00:00Z" }),
      note({ id: "new", title: "Latest", updated_at: "2026-02-01T00:00:00Z" }),
    ]);
    renderPanel();

    const items = await screen.findAllByRole("listitem");
    expect(items[0]).toHaveTextContent("Latest");
    expect(items[1]).toHaveTextContent("Ohne Titel");
  });

  it("creates a note via the inline form", async () => {
    vi.mocked(api.people.privateNotes.list).mockResolvedValueOnce([]).mockResolvedValueOnce([note()]);
    vi.mocked(api.people.privateNotes.create).mockResolvedValue(note());
    renderPanel();

    await screen.findByText("Noch keine Notizen");
    fireEvent.click(screen.getByRole("button", { name: /Erste Notiz erstellen/ }));
    fireEvent.change(screen.getByLabelText("Inhalt"), { target: { value: "Very grounded energy." } });
    fireEvent.click(screen.getByRole("button", { name: "Speichern" }));

    expect(await screen.findByText("First impression")).toBeInTheDocument();
    expect(api.people.privateNotes.create).toHaveBeenCalledWith(PERSON_A, {
      title: null,
      content: "Very grounded energy.",
    });
  });

  it("opens inline edit on row click and patches only on save", async () => {
    vi.mocked(api.people.privateNotes.list).mockResolvedValue([note()]);
    renderPanel();
    fireEvent.click(await screen.findByText("First impression"));

    const contentBox = screen.getByDisplayValue("Very grounded energy.");
    fireEvent.change(contentBox, { target: { value: "Updated." } });
    fireEvent.click(screen.getByRole("button", { name: "Speichern" }));

    expect(api.people.privateNotes.patch).toHaveBeenCalledWith("note-1", {
      title: "First impression",
      content: "Updated.",
    });
  });

  it("requires a two-step inline confirmation before deleting", async () => {
    vi.mocked(api.people.privateNotes.list).mockResolvedValue([note()]);
    renderPanel();
    const item = (await screen.findByText("First impression")).closest("li")!;

    fireEvent.click(within(item).getByRole("button", { name: "Löschen" }));
    expect(api.people.privateNotes.remove).not.toHaveBeenCalled();
    fireEvent.click(within(item).getByRole("button", { name: "Endgültig löschen" }));
    expect(api.people.privateNotes.remove).toHaveBeenCalledWith("note-1");
  });
});
