import { useState } from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ErrorBoundary } from "@/components/ui/error-boundary";
import { LocaleProvider } from "@/i18n/context";

function Bomb({ armed }: { armed: boolean }) {
  if (armed) throw new Error("boom");
  return <p>fine</p>;
}

function Harness() {
  const [armed, setArmed] = useState(true);
  return (
    <div>
      <ErrorBoundary>
        <Bomb armed={armed} />
      </ErrorBoundary>
      <button onClick={() => setArmed(false)}>disarm</button>
    </div>
  );
}

describe("ErrorBoundary", () => {
  it("renders children when nothing throws", () => {
    render(
      <LocaleProvider>
        <ErrorBoundary>
          <Bomb armed={false} />
        </ErrorBoundary>
      </LocaleProvider>,
    );
    expect(screen.getByText("fine")).toBeInTheDocument();
  });

  it("shows a fallback instead of the whole page crashing, and recovers on retry", () => {
    const consoleError = vi.spyOn(console, "error").mockImplementation(() => {});
    render(
      <LocaleProvider>
        <Harness />
      </LocaleProvider>,
    );

    expect(screen.getByRole("alert")).toHaveTextContent("Etwas ist schiefgelaufen");

    // Fixing the underlying condition alone doesn't un-render the fallback -- the
    // boundary only re-attempts the subtree once the user asks it to.
    fireEvent.click(screen.getByRole("button", { name: "disarm" }));
    expect(screen.getByRole("alert")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Erneut versuchen" }));
    expect(screen.getByText("fine")).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    consoleError.mockRestore();
  });
});
