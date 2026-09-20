import { act, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AuthProvider, useAuth } from "@/lib/auth-context";
import { api, ApiError, NetworkError, type UserOut } from "@/api/client";

/**
 * Targeted coverage for the branches of AuthProvider that the register/me tests in
 * auth-context.test.tsx leave untested (PWA-08, #140): login success, login rejection
 * with an API error, login rejection with a non-API failure, and logout dropping the
 * local session even when the API call itself fails. These are the auth/error-state
 * branches where a silent regression would either strand a signed-in-looking shell or
 * keep a session alive client-side after a failed sign-out.
 */
vi.mock("@/api/client", async () => {
  const actual = await vi.importActual<typeof import("@/api/client")>("@/api/client");
  return {
    ...actual,
    api: { auth: { me: vi.fn(), login: vi.fn(), register: vi.fn(), logout: vi.fn() } },
  };
});

const signedInUser: UserOut = {
  id: "u1",
  email: "ada@example.com",
  role: "USER",
  is_active: true,
};

function Probe() {
  const { status, user, error, login, register, logout } = useAuth();
  return (
    <div>
      <p data-testid="status">{status}</p>
      <p data-testid="email">{user?.email ?? "none"}</p>
      <p data-testid="error">{error ?? "none"}</p>
      <button
        onClick={() => {
          void login("ada@example.com", "a-strong-password").catch(() => {
            /* surfaced via the error state; the click handler itself must not throw */
          });
        }}
      >
        login
      </button>
      <button
        onClick={() => {
          void register("ada@example.com", "a-strong-password").catch(() => {
            /* see login: the error is surfaced through the provider's error state */
          });
        }}
      >
        register
      </button>
      <button
        onClick={() => {
          void logout().catch(() => {
            /* the provider drops the local session in `finally` regardless; swallow
               here so the click handler itself never throws into the event dispatch */
          });
        }}
      >
        logout
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

async function click(name: string) {
  await act(async () => {
    screen.getByRole("button", { name }).click();
  });
}

describe("AuthProvider.login / register", () => {
  beforeEach(() => {
    vi.mocked(api.auth.me)
      .mockReset()
      .mockRejectedValue(new ApiError("no session", "UNAUTHENTICATED", 401));
    vi.mocked(api.auth.login).mockReset();
    vi.mocked(api.auth.register).mockReset();
    vi.mocked(api.auth.logout).mockReset().mockResolvedValue(undefined);
  });

  it("sets the user and status=authenticated on success", async () => {
    vi.mocked(api.auth.login).mockResolvedValue(signedInUser);
    renderProbe();
    await screen.findByText("anonymous");

    await click("login");

    expect(await screen.findByTestId("status")).toHaveTextContent("authenticated");
    expect(screen.getByTestId("email")).toHaveTextContent("ada@example.com");
    expect(screen.getByTestId("error")).toHaveTextContent("none");
  });

  it("stays anonymous and surfaces the API message when the credentials are rejected", async () => {
    vi.mocked(api.auth.login).mockRejectedValue(
      new ApiError("E-Mail oder Passwort ist falsch.", "INVALID_CREDENTIALS", 401),
    );
    renderProbe();
    await screen.findByText("anonymous");

    await click("login");

    expect(screen.getByTestId("status")).toHaveTextContent("anonymous");
    expect(screen.getByTestId("email")).toHaveTextContent("none");
    expect(screen.getByTestId("error")).toHaveTextContent("E-Mail oder Passwort ist falsch.");
  });

  it("stays anonymous and records an error for a non-API failure (network)", async () => {
    vi.mocked(api.auth.login).mockRejectedValue(new NetworkError(new Error("offline")));
    renderProbe();
    await screen.findByText("anonymous");

    await click("login");

    expect(screen.getByTestId("status")).toHaveTextContent("anonymous");
    expect(screen.getByTestId("email")).toHaveTextContent("none");
    // Deliberately not pinning the exact fallback wording here (it is currently the
    // hardcoded English "Login failed.", while errors from the API are German) --
    // what matters for this branch is that *some* error reaches the UI.
    expect(screen.getByTestId("error")).not.toHaveTextContent("none");
  });

  it("register records an error for a non-API failure (network)", async () => {
    vi.mocked(api.auth.register).mockRejectedValue(new NetworkError(new Error("offline")));
    renderProbe();
    await screen.findByText("anonymous");

    await click("register");

    expect(screen.getByTestId("status")).toHaveTextContent("anonymous");
    expect(screen.getByTestId("email")).toHaveTextContent("none");
    expect(screen.getByTestId("error")).not.toHaveTextContent("none");
  });
});

describe("AuthProvider.logout", () => {
  beforeEach(() => {
    vi.mocked(api.auth.me).mockReset().mockResolvedValue(signedInUser);
    vi.mocked(api.auth.login).mockReset();
    vi.mocked(api.auth.register).mockReset();
    vi.mocked(api.auth.logout).mockReset();
  });

  it("drops the local session even when the API call fails", async () => {
    vi.mocked(api.auth.logout).mockRejectedValue(new NetworkError(new Error("offline")));
    renderProbe();
    await screen.findByText("authenticated");

    await click("logout");

    expect(screen.getByTestId("status")).toHaveTextContent("anonymous");
    expect(screen.getByTestId("email")).toHaveTextContent("none");
  });
});
