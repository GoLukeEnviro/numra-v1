import { act, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AuthProvider, useAuth } from "@/lib/auth-context";
import { api, ApiError, type UserOut } from "@/api/client";

vi.mock("@/api/client", async () => {
  const actual = await vi.importActual<typeof import("@/api/client")>("@/api/client");
  return { ...actual, api: { auth: { me: vi.fn(), register: vi.fn() } } };
});

const registeredUser: UserOut = {
  id: "u1",
  email: "ada@example.com",
  role: "USER",
  is_active: true,
};

function Probe() {
  const { status, user, error, register } = useAuth();
  return (
    <div>
      <p data-testid="status">{status}</p>
      <p data-testid="email">{user?.email ?? "none"}</p>
      <p data-testid="error">{error ?? "none"}</p>
      <button
        onClick={() => {
          void register("ada@example.com", "a-strong-password").catch(() => {
            /* surfaced via error state; swallow here so the click handler itself
               never throws inside the test's synthetic event dispatch */
          });
        }}
      >
        register
      </button>
    </div>
  );
}

function renderProbe() {
  return render(
    <AuthProvider>
      <Probe />
    </AuthProvider>,
  );
}

describe("AuthProvider.register", () => {
  beforeEach(() => {
    vi.mocked(api.auth.me).mockReset().mockRejectedValue(new ApiError("no session", "UNAUTHENTICATED", 401));
    vi.mocked(api.auth.register).mockReset();
  });

  it("sets the user and status=authenticated on success (auto-login)", async () => {
    vi.mocked(api.auth.register).mockResolvedValue(registeredUser);
    renderProbe();

    await screen.findByText("anonymous");

    await act(async () => {
      screen.getByRole("button", { name: "register" }).click();
    });

    expect(await screen.findByTestId("status")).toHaveTextContent("authenticated");
    expect(screen.getByTestId("email")).toHaveTextContent("ada@example.com");
  });

  it("stays anonymous and records the error when registration fails", async () => {
    vi.mocked(api.auth.register).mockRejectedValue(
      new ApiError("Diese E-Mail ist bereits vergeben.", "EMAIL_ALREADY_REGISTERED", 409),
    );
    renderProbe();

    await screen.findByText("anonymous");

    await act(async () => {
      screen.getByRole("button", { name: "register" }).click();
    });

    expect(await screen.findByTestId("status")).toHaveTextContent("anonymous");
    expect(screen.getByTestId("email")).toHaveTextContent("none");
    expect(screen.getByTestId("error")).toHaveTextContent("Diese E-Mail ist bereits vergeben.");
  });
});
