import { describe, expect, it } from "vitest";

import { launchReducer, initialLaunchState } from "../screens/launch-state";

describe("launchReducer", () => {
  it("moves from loading to ready with the validated brand", () => {
    expect(
      launchReducer(initialLaunchState, {
        type: "ready",
        config: { brandName: "AVENYTH", allowSelfSignup: true },
      }),
    ).toEqual({
      status: "ready",
      config: { brandName: "AVENYTH", allowSelfSignup: true },
    });
  });

  it("keeps configuration failures distinct from service failures", () => {
    expect(launchReducer(initialLaunchState, { type: "misconfigured", message: "URL missing" }))
      .toEqual({ status: "misconfigured", message: "URL missing" });
    expect(launchReducer(initialLaunchState, { type: "unavailable" })).toEqual({
      status: "unavailable",
    });
  });

  it("returns to loading when retrying", () => {
    expect(launchReducer({ status: "unavailable" }, { type: "retry" })).toEqual({
      status: "loading",
    });
  });
});
