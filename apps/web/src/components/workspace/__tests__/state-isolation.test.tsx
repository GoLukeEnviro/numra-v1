import { render, screen, waitFor } from "@testing-library/react";
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
const PERSON_B = "person-b";

function noteFor(personId: string, text: string): PrivateNoteOut {
  return {
    id: `${personId}-note`,
    person_id: personId,
    title: null,
    content: text,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
  };
}

/**
 * Privacy-critical (PR-WEB-02 step 9): switching the active person must clear
 * stale data immediately, not only after the new response lands, and must never
 * let a slow, stale response for the old person leak into the new person's view.
 */
describe("Personal Workspace state isolation across a person switch", () => {
  beforeEach(() => {
    vi.mocked(api.people.privateNotes.list).mockReset();
  });

  it("clears Person A's notes immediately and shows only Person B's data once loaded", async () => {
    let resolveA: (notes: PrivateNoteOut[]) => void = () => {};
    const personAPromise = new Promise<PrivateNoteOut[]>((resolve) => {
      resolveA = resolve;
    });
    vi.mocked(api.people.privateNotes.list).mockImplementationOnce(() => personAPromise);

    const { rerender } = render(
      <LocaleProvider>
        <PrivateNotesPanel personId={PERSON_A} managedProfile={false} />
      </LocaleProvider>,
    );

    resolveA([noteFor(PERSON_A, "Person A's secret note")]);
    expect(await screen.findByText("Person A's secret note")).toBeInTheDocument();

    // A slow, still-pending response for Person B -- the switch must not wait for it
    // to clear Person A's content from the DOM.
    let resolveB: (notes: PrivateNoteOut[]) => void = () => {};
    const personBPromise = new Promise<PrivateNoteOut[]>((resolve) => {
      resolveB = resolve;
    });
    vi.mocked(api.people.privateNotes.list).mockImplementationOnce(() => personBPromise);

    rerender(
      <LocaleProvider>
        <PrivateNotesPanel personId={PERSON_B} managedProfile={false} />
      </LocaleProvider>,
    );

    // Person A's data is gone immediately, before Person B's request resolves.
    expect(screen.queryByText("Person A's secret note")).not.toBeInTheDocument();
    expect(screen.getByRole("status")).toBeInTheDocument();

    resolveB([noteFor(PERSON_B, "Person B's own note")]);

    await waitFor(() => expect(screen.getByText("Person B's own note")).toBeInTheDocument());
    expect(screen.queryByText("Person A's secret note")).not.toBeInTheDocument();
  });

  it("discards a stale Person A response that resolves after the switch to Person B", async () => {
    let resolveA: (notes: PrivateNoteOut[]) => void = () => {};
    const personAPromise = new Promise<PrivateNoteOut[]>((resolve) => {
      resolveA = resolve;
    });
    vi.mocked(api.people.privateNotes.list).mockImplementationOnce(() => personAPromise);

    const { rerender } = render(
      <LocaleProvider>
        <PrivateNotesPanel personId={PERSON_A} managedProfile={false} />
      </LocaleProvider>,
    );

    // Switch to Person B before A's request has resolved at all.
    vi.mocked(api.people.privateNotes.list).mockResolvedValueOnce([noteFor(PERSON_B, "Person B's own note")]);
    rerender(
      <LocaleProvider>
        <PrivateNotesPanel personId={PERSON_B} managedProfile={false} />
      </LocaleProvider>,
    );

    await waitFor(() => expect(screen.getByText("Person B's own note")).toBeInTheDocument());

    // Person A's stale response finally resolves -- it must never override B's view.
    resolveA([noteFor(PERSON_A, "Person A's secret note")]);
    await new Promise((r) => setTimeout(r, 0));

    expect(screen.queryByText("Person A's secret note")).not.toBeInTheDocument();
    expect(screen.getByText("Person B's own note")).toBeInTheDocument();
  });
});
