import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { ContentFlagNotice } from "@/components/ui/content-flag-notice";
import { LocaleProvider } from "@/i18n/context";

function renderNotice(props: Parameters<typeof ContentFlagNotice>[0]) {
  return render(
    <LocaleProvider>
      <ContentFlagNotice {...props} />
    </LocaleProvider>,
  );
}

describe("ContentFlagNotice", () => {
  it("renders nothing for unflagged or unknown content", () => {
    const { container, rerender } = renderNotice({ flag: "none" });
    expect(container).toBeEmptyDOMElement();
    rerender(
      <LocaleProvider>
        <ContentFlagNotice flag={undefined} />
      </LocaleProvider>,
    );
    expect(container).toBeEmptyDOMElement();
  });

  it("states that the content contains technical placeholders and keeps the original", () => {
    renderNotice({ flag: "unresolved_template_tokens" });
    expect(screen.getByRole("note")).toBeInTheDocument();
    expect(screen.getByText("Dieser Inhalt enthält technische Platzhalter")).toBeInTheDocument();
    expect(screen.getByText(/Das Original bleibt erhalten/)).toBeInTheDocument();
  });

  it("renders the explicit action slot only when flagged", () => {
    renderNotice({
      flag: "unresolved_template_tokens",
      action: <button type="button">Neu erzeugen</button>,
    });
    expect(screen.getByRole("button", { name: "Neu erzeugen" })).toBeInTheDocument();
  });
});
