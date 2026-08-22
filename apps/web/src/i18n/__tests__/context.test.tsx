import { describe, expect, it, beforeEach } from "vitest";
import { render, screen, fireEvent, act } from "@testing-library/react";
import { LocaleProvider, useLocale } from "@/i18n/context";

function Probe() {
  const { locale, setLocale, t } = useLocale();
  return (
    <div>
      <p data-testid="locale">{locale}</p>
      <p data-testid="label">{t("nav.today")}</p>
      <button onClick={() => setLocale("en")}>switch to en</button>
    </div>
  );
}

describe("LocaleProvider / useLocale", () => {
  beforeEach(() => {
    window.localStorage.clear();
    document.documentElement.lang = "";
  });

  it("defaults to German when no preference is stored", async () => {
    render(
      <LocaleProvider>
        <Probe />
      </LocaleProvider>,
    );
    expect(await screen.findByTestId("locale")).toHaveTextContent("de");
    expect(screen.getByTestId("label")).toHaveTextContent("Heute");
  });

  it("switches to English, translates immediately, and persists the choice", async () => {
    render(
      <LocaleProvider>
        <Probe />
      </LocaleProvider>,
    );
    await screen.findByTestId("locale");

    act(() => {
      fireEvent.click(screen.getByText("switch to en"));
    });

    expect(screen.getByTestId("locale")).toHaveTextContent("en");
    expect(screen.getByTestId("label")).toHaveTextContent("Today");
    expect(document.documentElement.lang).toBe("en");
    expect(window.localStorage.getItem("numra:locale:v1")).toBe("en");
  });

  it("restores a previously chosen locale on remount", async () => {
    window.localStorage.setItem("numra:locale:v1", "en");
    render(
      <LocaleProvider>
        <Probe />
      </LocaleProvider>,
    );
    expect(await screen.findByTestId("locale")).toHaveTextContent("en");
    expect(screen.getByTestId("label")).toHaveTextContent("Today");
  });
});
