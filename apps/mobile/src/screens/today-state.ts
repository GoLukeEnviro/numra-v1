import type { DailyBrief, Timing, TodayPerson } from "../api/today-client";

export type TodayState =
  | { status: "loading" }
  | { status: "ready"; person: TodayPerson; timing: Timing; brief: DailyBrief }
  | { status: "noPerson" }
  | { status: "error"; message: string }
  | { status: "unauthorized" };

export type TodayAction =
  | { type: "loaded"; person: TodayPerson; timing: Timing; brief: DailyBrief }
  | { type: "failed"; message: string }
  | { type: "noPerson" }
  | { type: "unauthorized" };

export const initialTodayState: TodayState = { status: "loading" };

export function todayReducer(_state: TodayState, action: TodayAction): TodayState {
  switch (action.type) {
    case "loaded":
      return { status: "ready", person: action.person, timing: action.timing, brief: action.brief };
    case "failed":
      return { status: "error", message: action.message };
    case "noPerson":
      return { status: "noPerson" };
    case "unauthorized":
      return { status: "unauthorized" };
  }
}
