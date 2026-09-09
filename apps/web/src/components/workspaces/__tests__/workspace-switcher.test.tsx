import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { WorkspaceSwitcher, type WorkspaceOption } from "@/components/workspaces/workspace-switcher";
import { LocaleProvider } from "@/i18n/context";

const OPTIONS: WorkspaceOption[] = [
  { id: "ws-1", label: "Lukas", kind: "PERSONAL" },
  { id: "ws-2", label: "Lukas & Mira", kind: "RELATIONSHIP" },
];

function renderSwitcher(onSelect: (id: string) => void, activeId: string | null = "ws-1") {
  return render(
    <LocaleProvider>
      <WorkspaceSwitcher options={OPTIONS} activeId={activeId} onSelect={onSelect} />
    </LocaleProvider>,
  );
}

describe("WorkspaceSwitcher", () => {
  it("calls onSelect with the chosen workspace id when the select changes", () => {
    const onSelect = vi.fn();
    renderSwitcher(onSelect);

    fireEvent.change(screen.getByRole("combobox"), { target: { value: "ws-2" } });

    expect(onSelect).toHaveBeenCalledWith("ws-2");
  });

  it("exposes a localized aria-label and prefixes the PERSONAL option's label", () => {
    renderSwitcher(vi.fn());

    const select = screen.getByRole("combobox", { name: "Workspace wechseln" });
    expect(select).toBeInTheDocument();
    expect(screen.getByText("Persönlicher Bereich — Lukas")).toBeInTheDocument();
    expect(screen.getByText("Lukas & Mira")).toBeInTheDocument();
  });
});
