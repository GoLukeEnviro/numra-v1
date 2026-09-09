import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import {
  ComingSoonState,
  PhaseDisabledState,
  type PhaseErrorCode,
} from "@/components/ui/states";

const CODES: PhaseErrorCode[] = [
  "V2_DISABLED",
  "V2_PHASE_DISABLED",
  "WORKSPACE_DISSOLVED",
  "KNOWLEDGE_FRAME_NOT_AVAILABLE",
  "CONSENT_NOT_GRANTED",
];

describe("PhaseDisabledState", () => {
  it.each(CODES)("renders %s with role=status, no retry button", (code) => {
    render(<PhaseDisabledState code={code} title={`Titel für ${code}`} description="Beschreibung" />);

    expect(screen.getByRole("status")).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
    expect(screen.getByText(`Titel für ${code}`)).toBeInTheDocument();
    expect(screen.getByText("Beschreibung")).toBeInTheDocument();
  });

  // Replaces the removed /dev/pr-web-00-demo Playwright screenshot (f): all 5 codes
  // rendered simultaneously, none clobbering another's status region or copy.
  it("renders all 5 codes simultaneously without collisions", () => {
    render(
      <>
        {CODES.map((code) => (
          <PhaseDisabledState key={code} code={code} title={`Titel für ${code}`} description={`Beschreibung ${code}`} />
        ))}
      </>,
    );

    expect(screen.getAllByRole("status")).toHaveLength(CODES.length);
    for (const code of CODES) {
      expect(screen.getByText(`Titel für ${code}`)).toBeInTheDocument();
      expect(screen.getByText(`Beschreibung ${code}`)).toBeInTheDocument();
    }
  });
});

describe("ComingSoonState", () => {
  it("renders title and body", () => {
    render(<ComingSoonState title="Bald verfügbar" description="Noch nicht angebunden." />);

    expect(screen.getByText("Bald verfügbar")).toBeInTheDocument();
    expect(screen.getByText("Noch nicht angebunden.")).toBeInTheDocument();
  });
});
