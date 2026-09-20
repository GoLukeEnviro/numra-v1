import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ExportAccountPanel } from "@/components/settings/export-account-panel";
import { LocaleProvider } from "@/i18n/context";

/**
 * The account-data export must be reachable through the real product surface and it
 * must be honest about what it contains: a same-origin download link (the API answers
 * with the attachment filename) plus the explicit statement that no credentials,
 * sessions, tokens or prompt scaffolding travel with it.
 */
describe("ExportAccountPanel", () => {
  it("offers a same-origin download link to the account export", () => {
    render(
      <LocaleProvider>
        <ExportAccountPanel />
      </LocaleProvider>,
    );

    const link = screen.getByRole("link", { name: /Daten herunterladen/ });

    expect(link).toHaveAttribute("href", "/api/v1/account/export");
    expect(link).toHaveAttribute("download");
  });

  it("states that the export carries only this account and no secrets", () => {
    render(
      <LocaleProvider>
        <ExportAccountPanel />
      </LocaleProvider>,
    );

    const disclosure = screen.getByText(/ausschließlich Daten dieses Kontos/);

    expect(disclosure).toHaveTextContent("Passwörter");
    expect(disclosure).toHaveTextContent("Prompt-Bausteine");
    expect(screen.getByText(/avenyth-account-export-/)).toBeInTheDocument();
  });
});
