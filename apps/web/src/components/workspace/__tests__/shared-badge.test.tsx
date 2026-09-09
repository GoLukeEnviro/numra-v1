import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { SharedBadge } from "@/components/workspace/shared-badge";
import { LocaleProvider } from "@/i18n/context";

describe("SharedBadge", () => {
  it("renders the localized shared-content label", () => {
    render(
      <LocaleProvider>
        <SharedBadge />
      </LocaleProvider>,
    );
    expect(screen.getByText("Geteilt")).toBeInTheDocument();
  });
});
