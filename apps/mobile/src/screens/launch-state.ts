import type { MobilePublicConfig } from "../api/public-config";

export type LaunchState =
  | { status: "loading" }
  | { status: "ready"; config: MobilePublicConfig }
  | { status: "misconfigured"; message: string }
  | { status: "unavailable" };

export type LaunchAction =
  | { type: "ready"; config: MobilePublicConfig }
  | { type: "misconfigured"; message: string }
  | { type: "unavailable" }
  | { type: "retry" };

export const initialLaunchState: LaunchState = { status: "loading" };

export function launchReducer(_state: LaunchState, action: LaunchAction): LaunchState {
  switch (action.type) {
    case "ready":
      return { status: "ready", config: action.config };
    case "misconfigured":
      return { status: "misconfigured", message: action.message };
    case "unavailable":
      return { status: "unavailable" };
    case "retry":
      return initialLaunchState;
  }
}

