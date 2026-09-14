import { describe, expect, it } from "vitest";

import { initialTodayState, todayReducer } from "../screens/today-state";
import type { DailyBrief, Timing, TodayPerson } from "../api/today-client";

const person: TodayPerson = { id: "p1", birth_first_names: "Lukas", preferred_name: null };

const timing: Timing = {
  personal_year: { display_value: "17/8" },
  personal_month: { display_value: "16/7" },
  personal_day: { display_value: "8" },
};

const brief: DailyBrief = {
  person_id: "p1",
  as_of_date: "2026-08-19",
  knowledge_version: "1.0.0",
  sections: [
    { metric_id: "personal_day", display_name_de: "Persönlicher Tag", display_value: "8", text_de: "Text." },
  ],
};

describe("todayReducer", () => {
  it("starts by loading and carries both payloads into the ready state", () => {
    expect(initialTodayState).toEqual({ status: "loading" });
    expect(todayReducer(initialTodayState, { type: "loaded", person, timing, brief })).toEqual({
      status: "ready",
      person,
      timing,
      brief,
    });
  });

  it("keeps an empty account distinct from a failure", () => {
    expect(todayReducer(initialTodayState, { type: "noPerson" })).toEqual({ status: "noPerson" });
    expect(todayReducer(initialTodayState, { type: "failed", message: "Keine Verbindung." })).toEqual({
      status: "error",
      message: "Keine Verbindung.",
    });
  });

  it("keeps a rejected credential distinct from a transport failure", () => {
    expect(todayReducer(initialTodayState, { type: "unauthorized" })).toEqual({
      status: "unauthorized",
    });
  });

  it("replaces a previous result on every transition, so stale content is never shown", () => {
    const ready = todayReducer(initialTodayState, { type: "loaded", person, timing, brief });
    expect(todayReducer(ready, { type: "failed", message: "Abbruch." })).toEqual({
      status: "error",
      message: "Abbruch.",
    });
    expect(todayReducer(ready, { type: "unauthorized" })).toEqual({ status: "unauthorized" });
    expect(todayReducer(ready, { type: "noPerson" })).toEqual({ status: "noPerson" });
  });
});
