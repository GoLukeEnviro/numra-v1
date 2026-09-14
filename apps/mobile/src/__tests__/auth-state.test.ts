import { describe, expect, it } from "vitest";

import { authReducer, initialAuthState } from "../auth/auth-state";

const user = { id: "u1", email: "mobile@example.com", role: "USER", is_active: true };

describe("authReducer", () => {
  it("restores into signed-out or signed-in state", () => {
    expect(authReducer(initialAuthState, { type: "restored", user: null })).toEqual({ status: "signedOut" });
    expect(authReducer(initialAuthState, { type: "restored", user })).toEqual({ status: "signedIn", user });
  });

  it("keeps invalid credentials actionable", () => {
    expect(authReducer({ status: "signingIn" }, { type: "failed", message: "E-Mail oder Passwort falsch" })).toEqual({
      status: "signedOut",
      error: "E-Mail oder Passwort falsch",
    });
  });

  it("returns to signed out after logout", () => {
    expect(authReducer({ status: "signedIn", user }, { type: "signedOut" })).toEqual({ status: "signedOut" });
  });
});
