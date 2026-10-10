import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { RegenerateControl } from "@/components/ui/regenerate-control";
import { ApiError, type RegenerationPreviewOut } from "@/api/client";
import { LocaleProvider } from "@/i18n/context";

const preview: RegenerationPreviewOut = {
  content_flag: "unresolved_template_tokens",
  can_regenerate: true,
  blocked_reason: null,
  existing_regeneration_id: null,
  uses_llm: true,
  feature: "report",
  units: 1,
  original_kept: true,
  quota: {
    window_limit: 3,
    window_seconds: 3600,
    used_in_window: 1,
    concurrent_limit: null,
    active: 0,
    would_exceed: false,
  },
};

function setup(overrides: {
  preview?: RegenerationPreviewOut;
  start?: (key: string) => Promise<{ id: string }>;
}) {
  const loadPreview = vi.fn().mockResolvedValue(overrides.preview ?? preview);
  const start = vi.fn(overrides.start ?? (() => Promise.resolve({ id: "new-1" })));
  const onStarted = vi.fn();
  const onOpenExisting = vi.fn();
  render(
    <LocaleProvider>
      <RegenerateControl
        loadPreview={loadPreview}
        start={start}
        onStarted={onStarted}
        onOpenExisting={onOpenExisting}
      />
    </LocaleProvider>,
  );
  return { loadPreview, start, onStarted, onOpenExisting };
}

async function openPreview() {
  fireEvent.click(screen.getByRole("button", { name: "Neu erzeugen" }));
  await screen.findByTestId("regenerate-preview");
}

describe("RegenerateControl", () => {
  it("only loads the preview on the first click and starts nothing", async () => {
    const { loadPreview, start } = setup({});
    await openPreview();

    expect(loadPreview).toHaveBeenCalledTimes(1);
    expect(start).not.toHaveBeenCalled();
    expect(screen.getByText(/mit dem Sprachmodell erzeugt/)).toBeInTheDocument();
    expect(screen.getByText(/verbraucht eine Einheit/)).toBeInTheDocument();
    expect(screen.getByText(/Bereits genutzt: 1 von 3/)).toBeInTheDocument();
    expect(screen.getByText(/Das Original bleibt unverändert/)).toBeInTheDocument();
  });

  it("starts exactly once on a double click and hands the result on", async () => {
    let resolve: (value: { id: string }) => void = () => {};
    const { start, onStarted } = setup({
      start: () => new Promise((r) => (resolve = r)),
    });
    await openPreview();

    const confirm = screen.getByRole("button", { name: "Jetzt neu erzeugen" });
    fireEvent.click(confirm);
    fireEvent.click(confirm);
    resolve({ id: "new-1" });

    await waitFor(() => expect(onStarted).toHaveBeenCalledWith({ id: "new-1" }));
    expect(start).toHaveBeenCalledTimes(1);
    expect(typeof start.mock.calls[0]?.[0]).toBe("string");
  });

  it("disables the start while the limit is reached", async () => {
    setup({
      preview: { ...preview, quota: { ...preview.quota!, would_exceed: true } },
    });
    await openPreview();

    expect(screen.getByRole("button", { name: "Jetzt neu erzeugen" })).toBeDisabled();
    expect(screen.getByText(/Limit ist aktuell erreicht/)).toBeInTheDocument();
  });

  it("offers the existing version instead of a second start", async () => {
    const { start, onOpenExisting } = setup({
      preview: {
        ...preview,
        can_regenerate: false,
        blocked_reason: "ALREADY_REGENERATED",
        existing_regeneration_id: "existing-9",
      },
    });
    await openPreview();

    expect(screen.queryByRole("button", { name: "Jetzt neu erzeugen" })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Neue Version öffnen" }));
    expect(onOpenExisting).toHaveBeenCalledWith("existing-9");
    expect(start).not.toHaveBeenCalled();
  });

  it("shows the error code and re-sends the same key on retry", async () => {
    const start = vi
      .fn()
      .mockRejectedValueOnce(new ApiError("Limit erreicht", "QUOTA_EXCEEDED", 429))
      .mockResolvedValueOnce({ id: "new-2" });
    const { onStarted } = setup({ start });
    await openPreview();

    fireEvent.click(screen.getByRole("button", { name: "Jetzt neu erzeugen" }));
    expect(await screen.findByText("QUOTA_EXCEEDED")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Jetzt neu erzeugen" }));
    await waitFor(() => expect(onStarted).toHaveBeenCalledWith({ id: "new-2" }));
    expect(start.mock.calls[0]?.[0]).toBe(start.mock.calls[1]?.[0]);
  });

  it("reports a failed preview and stays closed", async () => {
    const loadPreview = vi.fn().mockRejectedValue(new ApiError("Nicht erlaubt", "FORBIDDEN", 403));
    render(
      <LocaleProvider>
        <RegenerateControl
          loadPreview={loadPreview}
          start={vi.fn()}
          onStarted={vi.fn()}
          onOpenExisting={vi.fn()}
        />
      </LocaleProvider>,
    );

    fireEvent.click(screen.getByRole("button", { name: "Neu erzeugen" }));

    expect(await screen.findByText("FORBIDDEN")).toBeInTheDocument();
    expect(screen.queryByTestId("regenerate-preview")).not.toBeInTheDocument();
  });
});
