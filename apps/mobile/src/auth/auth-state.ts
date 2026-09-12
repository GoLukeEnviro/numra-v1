import type { MobileUser } from "../api/auth-client";

export type AuthState =
  | { status: "restoring" }
  | { status: "signedOut"; error?: string }
  | { status: "signingIn" }
  | { status: "signedIn"; user: MobileUser };

export type AuthAction =
  | { type: "restored"; user: MobileUser | null }
  | { type: "signingIn" }
  | { type: "signedIn"; user: MobileUser }
  | { type: "failed"; message: string }
  | { type: "signedOut" };

export const initialAuthState: AuthState = { status: "restoring" };

export function authReducer(_state: AuthState, action: AuthAction): AuthState {
  switch (action.type) {
    case "restored": return action.user ? { status: "signedIn", user: action.user } : { status: "signedOut" };
    case "signingIn": return { status: "signingIn" };
    case "signedIn": return { status: "signedIn", user: action.user };
    case "failed": return { status: "signedOut", error: action.message };
    case "signedOut": return { status: "signedOut" };
  }
}
