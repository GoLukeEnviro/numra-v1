import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import LoginPage from "@/app/login/page";
import ForgotPasswordPage from "@/app/forgot-password/page";
import ResetPasswordPage from "@/app/reset-password/page";
import { useAuth } from "@/lib/auth-context";
import { LocaleProvider } from "@/i18n/context";

vi.mock("@/api/client", async () => {
  const actual = await vi.importActual<typeof import("@/api/client")>("@/api/client");
  return {
    ...actual,
    api: { auth: { forgotPassword: vi.fn(), resetPassword: vi.fn() } },
  };
});

vi.mock("@/lib/auth-context", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/auth-context")>();
  return { ...actual, useAuth: vi.fn() };
});

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
  useSearchParams: () => ({ get: () => null }),
}));

function renderPage(page: React.ReactElement) {
  return render(<LocaleProvider>{page}</LocaleProvider>);
}

/**
 * PWA-10 / #185: every public page must expose exactly one h1 that is part of the
 * document outline. The measured defect was structural rather than visual — the only
 * h1 on /login sat inside a `hidden lg:block` brand panel, so below the `lg`
 * breakpoint it existed in the DOM but was display:none; and /forgot-password and
 * /reset-password had no h1 at all.
 *
 * A jsdom test cannot evaluate the `lg:` media query, so "visible at 390px" is not
 * something it can assert. It CAN assert the structural invariant that held for both
 * viewports in the sweep: each page carries exactly one h1, and that h1 is not
 * inside an element the layout can hide. The end-to-end viewport check stays with
 * the Playwright a11y sweep, which is where the defect was found.
 */
function h1s(): HTMLElement[] {
  return screen.queryAllByRole("heading", { level: 1 });
}

/** The single h1 with a non-optional type -- after `expect(...).toHaveLength(1)` the
 *  compiler still sees `HTMLElement | undefined`, so the assertion is what narrows it. */
function soleH1(): HTMLElement {
  const headings = h1s();
  expect(headings).toHaveLength(1);
  const [first] = headings;
  if (!first) throw new Error("no h1 rendered");
  return first;
}

describe("public auth pages expose exactly one real h1 (#185)", () => {
  beforeEach(() => {
    vi.mocked(useAuth).mockReturnValue({
      status: "anonymous",
      user: null,
      error: null,
    } as ReturnType<typeof useAuth>);
  });

  it("/login has exactly one h1 and it is not inside a hideable brand panel", () => {
    renderPage(<LoginPage />);

    const h1 = soleH1();

    // The regression this pins: the h1 must never be a descendant of an element
    // carrying a responsive `hidden ... lg:block` class, which is display:none on
    // mobile and removes the heading from the accessibility tree there.
    const hideableAncestor = h1.closest("div.hidden, div.lg\\:block, [class*='hidden'][class*='lg:']");
    expect(hideableAncestor).toBeNull();
  });

  it("/forgot-password has exactly one h1", () => {
    renderPage(<ForgotPasswordPage />);
    expect(h1s()).toHaveLength(1);
  });

  it("/reset-password has exactly one h1", () => {
    renderPage(<ResetPasswordPage />);
    expect(h1s()).toHaveLength(1);
  });

  it("each h1 carries an accessible name", () => {
    renderPage(<LoginPage />);
    expect(soleH1().textContent?.trim().length ?? 0).toBeGreaterThan(0);
  });
});
