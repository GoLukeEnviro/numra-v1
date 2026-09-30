import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import NotFound from "@/app/not-found";
import RouteError from "@/app/error";
import { LocaleProvider } from "@/i18n/context";

function renderPage(page: React.ReactElement) {
  return render(<LocaleProvider>{page}</LocaleProvider>);
}

describe("404 page", () => {
  it("is German, branded, and links back to the home page", () => {
    renderPage(<NotFound />);
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("Diese Seite gibt es nicht.");
    expect(screen.getByRole("link", { name: "Zur Startseite" })).toHaveAttribute("href", "/");
  });
});

describe("route error boundary", () => {
  it("offers a retry and never renders the error message, only the digest", () => {
    const reset = vi.fn();
    const error = Object.assign(new Error("secret internal detail /srv/app"), { digest: "abc123" });
    renderPage(<RouteError error={error} reset={reset} />);

    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("Diese Ansicht konnte nicht geladen werden.");
    expect(screen.queryByText(/secret internal detail/)).not.toBeInTheDocument();
    expect(screen.getByText(/abc123/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Erneut versuchen" }));
    expect(reset).toHaveBeenCalledOnce();
  });
});
