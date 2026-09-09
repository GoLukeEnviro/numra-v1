import { fireEvent, render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { PersonalTasksPanel } from "@/components/workspace/personal-tasks-panel";
import { api, type PersonalTaskOut } from "@/api/client";
import { LocaleProvider } from "@/i18n/context";

vi.mock("@/api/client", async () => {
  const actual = await vi.importActual<typeof import("@/api/client")>("@/api/client");
  return {
    ...actual,
    api: {
      personalTasks: {
        list: vi.fn(),
        create: vi.fn(),
        patch: vi.fn(),
        remove: vi.fn(),
      },
    },
  };
});

const PERSON_A = "person-a";

function task(overrides: Partial<PersonalTaskOut> = {}): PersonalTaskOut {
  return {
    id: "task-1",
    person_id: PERSON_A,
    title: "Call the accountant",
    description: null,
    due_date: null,
    status: "ACTIVE",
    completed_at: null,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

function renderPanel(personId = PERSON_A, managedProfile = false) {
  return render(
    <LocaleProvider>
      <PersonalTasksPanel personId={personId} managedProfile={managedProfile} />
    </LocaleProvider>,
  );
}

describe("PersonalTasksPanel", () => {
  beforeEach(() => {
    vi.mocked(api.personalTasks.list).mockReset();
    vi.mocked(api.personalTasks.create).mockReset();
    vi.mocked(api.personalTasks.patch).mockReset();
    vi.mocked(api.personalTasks.remove).mockReset();
  });

  it("shows a loading state while the list request is in flight", () => {
    vi.mocked(api.personalTasks.list).mockReturnValue(new Promise(() => {}));
    renderPanel();
    expect(screen.getByRole("status")).toBeInTheDocument();
  });

  it("shows an error state with retry on failure", async () => {
    vi.mocked(api.personalTasks.list).mockRejectedValue(new Error("boom"));
    renderPanel();
    expect(await screen.findByRole("alert")).toHaveTextContent("boom");
    expect(screen.getByRole("button", { name: "Try again" })).toBeInTheDocument();
  });

  it("shows the empty state with a create CTA when there are no tasks", async () => {
    vi.mocked(api.personalTasks.list).mockResolvedValue([]);
    renderPanel();
    expect(await screen.findByText("Noch keine Aufgaben")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Erste Aufgabe erstellen/ })).toBeInTheDocument();
  });

  it("renders the task list", async () => {
    vi.mocked(api.personalTasks.list).mockResolvedValue([task()]);
    renderPanel();
    expect(await screen.findByText("Call the accountant")).toBeInTheDocument();
  });

  it("creates a new task via the inline form", async () => {
    vi.mocked(api.personalTasks.list).mockResolvedValueOnce([]).mockResolvedValueOnce([task()]);
    vi.mocked(api.personalTasks.create).mockResolvedValue(task());
    renderPanel();

    await screen.findByText("Noch keine Aufgaben");
    fireEvent.click(screen.getByRole("button", { name: /Erste Aufgabe erstellen/ }));
    fireEvent.change(screen.getByLabelText("Titel"), { target: { value: "Call the accountant" } });
    fireEvent.click(screen.getByRole("button", { name: "Speichern" }));

    expect(await screen.findByText("Call the accountant")).toBeInTheDocument();
    expect(api.personalTasks.create).toHaveBeenCalledWith(PERSON_A, {
      title: "Call the accountant",
      description: null,
      due_date: null,
    });
  });

  it("toggles a task from active to completed via the checkbox, never sending completed_at", async () => {
    vi.mocked(api.personalTasks.list)
      .mockResolvedValueOnce([task()])
      .mockResolvedValueOnce([task({ status: "COMPLETED" })]);
    vi.mocked(api.personalTasks.patch).mockResolvedValue(task({ status: "COMPLETED" }));
    renderPanel();

    const checkbox = await screen.findByRole("checkbox");
    fireEvent.click(checkbox);

    expect(api.personalTasks.patch).toHaveBeenCalledWith("task-1", { status: "COMPLETED" });
    const [, body] = vi.mocked(api.personalTasks.patch).mock.calls[0]!;
    expect(body).not.toHaveProperty("completed_at");
  });

  it("requires a two-step inline confirmation before deleting", async () => {
    vi.mocked(api.personalTasks.list).mockResolvedValue([task()]);
    renderPanel();
    await screen.findByText("Call the accountant");

    const item = screen.getByText("Call the accountant").closest("li")!;
    fireEvent.click(within(item).getByRole("button", { name: "Löschen" }));
    expect(api.personalTasks.remove).not.toHaveBeenCalled();

    fireEvent.click(within(item).getByRole("button", { name: "Endgültig löschen" }));
    expect(api.personalTasks.remove).toHaveBeenCalledWith("task-1");
  });

  it("uses managed-profile framing when managedProfile is true", async () => {
    vi.mocked(api.personalTasks.list).mockResolvedValue([]);
    renderPanel(PERSON_A, true);
    expect(await screen.findByText(/Nur in deinem Account sichtbar/)).toBeInTheDocument();
  });
});
