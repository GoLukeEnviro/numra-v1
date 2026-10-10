import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import ImpressumPage from "@/app/impressum/page";
import DatenschutzPage from "@/app/datenschutz/page";
import { LEGAL_OPERATOR } from "@/content/legal/operator";
import { LocaleProvider } from "@/i18n/context";

function renderPage(page: React.ReactElement) {
  return render(<LocaleProvider>{page}</LocaleProvider>);
}

describe("/impressum", () => {
  it("has exactly one h1 and the § 5 DDG block", () => {
    renderPage(<ImpressumPage />);
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
    expect(screen.getByRole("heading", { level: 2, name: "Angaben gemäß § 5 DDG" })).toBeInTheDocument();
  });

  it("renders the operator facts from content/legal/operator.ts", () => {
    const { container } = renderPage(<ImpressumPage />);
    const address = container.querySelector("address");
    expect(address).not.toBeNull();
    expect(address?.textContent).toContain(LEGAL_OPERATOR.country);
    expect(container.querySelector('a[href^="mailto:"]')).toHaveAttribute("href", `mailto:${LEGAL_OPERATOR.email}`);
  });

  it("omits the VAT line when there is no USt-IdNr. and links no ODR platform", () => {
    const { container } = renderPage(<ImpressumPage />);
    if (LEGAL_OPERATOR.vatId === null) {
      expect(screen.queryByText(/Umsatzsteuer-Identifikationsnummer/)).not.toBeInTheDocument();
    }
    expect(container.querySelector('a[href*="ec.europa.eu/consumers/odr"]')).toBeNull();
  });
});

describe("/datenschutz", () => {
  it("has exactly one h1", () => {
    renderPage(<DatenschutzPage />);
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
  });

  it("names every external recipient derived from the codebase", () => {
    const { container } = renderPage(<DatenschutzPage />);
    const text = container.textContent ?? "";
    for (const recipient of ["Cloudflare", "Resend", "Ollama Cloud", "Backblaze"]) {
      expect(text).toContain(recipient);
    }
  });

  it("states that names, birth dates and e-mail addresses are not sent to the LLM", () => {
    renderPage(<DatenschutzPage />);
    const section = screen.getByRole("region", { name: /KI-gestützte Formulierung/ });
    expect(within(section).getByText(/Namen, Geburtsdaten und E-Mail-Adressen werden nicht/)).toBeInTheDocument();
  });

  it("does not hard-code the session cookie name (it comes from server config)", () => {
    const { container } = renderPage(<DatenschutzPage />);
    expect(container.textContent).not.toMatch(/numra_session|numra_csrf/);
  });

  it("claims no hosting DPA and names no hosting provider until the operator confirms them", () => {
    const { container } = renderPage(<DatenschutzPage />);
    expect(container.textContent).not.toMatch(/Auftragsverarbeitung nach Art\. 28/);
  });
});
