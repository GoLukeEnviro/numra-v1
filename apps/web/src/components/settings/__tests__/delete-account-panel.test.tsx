import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { DeleteAccountPanel } from "@/components/settings/delete-account-panel";
import { LocaleProvider } from "@/i18n/context";
import { useAuth } from "@/lib/auth-context";

vi.mock("next/navigation", () => ({ useRouter: () => ({ replace: vi.fn() }) }));
vi.mock("@/lib/auth-context", () => ({ useAuth: vi.fn() }));

beforeEach(() => {
  vi.mocked(useAuth).mockReturnValue({ refresh: vi.fn() } as never);
});

describe("DeleteAccountPanel", () => {
  it("discloses retained pseudonymized shared history before account deletion", () => {
    render(<LocaleProvider><DeleteAccountPanel /></LocaleProvider>);

    fireEvent.click(screen.getByRole("button", { name: "Mein Konto löschen" }));

    expect(screen.getByText(/Gemeinsam erzeugte historische Inhalte/)).toHaveTextContent("pseudonymisiert");
    expect(screen.getByLabelText("Mit deinem Passwort bestätigen")).toBeInTheDocument();
  });
});
