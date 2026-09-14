import type { TokenStore } from "./auth-client";

export interface TodayPerson {
  id: string;
  birth_first_names: string;
  preferred_name?: string | null;
}

export interface TimingFigure {
  display_value: string;
}

export interface Timing {
  personal_year: TimingFigure;
  personal_month: TimingFigure;
  personal_day: TimingFigure;
}

export interface DailyBriefSection {
  metric_id: string;
  display_name_de: string;
  display_value: string;
  text_de: string;
}

export interface DailyBrief {
  person_id: string;
  as_of_date: string;
  knowledge_version: string;
  sections: DailyBriefSection[];
}

interface ResponseLike { ok: boolean; status: number; json(): Promise<unknown> }
type TodayFetcher = (input: string, init: RequestInit) => Promise<ResponseLike>;

/** The API expects the calendar day the user is actually living in, so this formats
 * the device's local date — `toISOString()` would silently report yesterday or
 * tomorrow for anyone east or west of UTC. */
export function todayIsoDate(now: Date = new Date()): string {
  const month = `${now.getMonth() + 1}`.padStart(2, "0");
  const day = `${now.getDate()}`.padStart(2, "0");
  return `${now.getFullYear()}-${month}-${day}`;
}

function isPerson(value: unknown): value is TodayPerson {
  return typeof value === "object" && value !== null &&
    "id" in value && typeof value.id === "string" &&
    "birth_first_names" in value && typeof value.birth_first_names === "string";
}

function isFigure(value: unknown): value is TimingFigure {
  return typeof value === "object" && value !== null &&
    "display_value" in value && typeof value.display_value === "string";
}

function isTiming(value: unknown): value is Timing {
  return typeof value === "object" && value !== null &&
    "personal_year" in value && isFigure(value.personal_year) &&
    "personal_month" in value && isFigure(value.personal_month) &&
    "personal_day" in value && isFigure(value.personal_day);
}

function isSection(value: unknown): value is DailyBriefSection {
  return typeof value === "object" && value !== null &&
    "metric_id" in value && typeof value.metric_id === "string" &&
    "display_name_de" in value && typeof value.display_name_de === "string" &&
    "display_value" in value && typeof value.display_value === "string" &&
    "text_de" in value && typeof value.text_de === "string";
}

function isDailyBrief(value: unknown): value is DailyBrief {
  return typeof value === "object" && value !== null &&
    "person_id" in value && typeof value.person_id === "string" &&
    "as_of_date" in value && typeof value.as_of_date === "string" &&
    "knowledge_version" in value && typeof value.knowledge_version === "string" &&
    "sections" in value && Array.isArray(value.sections) && value.sections.every(isSection);
}

/** Read-only access to the deterministic server-side Today surface. Every figure and
 * every sentence is rendered exactly as the API composed it — the native app performs
 * no numerology of its own, so it can never disagree with the web app. */
export function createTodayClient(origin: string, store: TokenStore, fetcher: TodayFetcher = fetch) {
  const bearer = (token: string) => ({ Authorization: `Bearer ${token}`, Accept: "application/json" });

  /** Throws `UNAUTHORIZED` for both "no credential" and "credential rejected"; the
   * caller owns the sign-out, mirroring how `auth-client.restore()` reacts to a 401. */
  async function read(path: string): Promise<unknown> {
    const token = await store.get();
    if (!token) throw new Error("UNAUTHORIZED");
    const response = await fetcher(`${origin}${path}`, { headers: bearer(token) });
    if (response.status === 401) throw new Error("UNAUTHORIZED");
    if (!response.ok) throw new Error("REQUEST_FAILED");
    return response.json();
  }

  return {
    async getFirstPerson(): Promise<TodayPerson | null> {
      const payload = await read("/v1/people");
      if (!Array.isArray(payload)) throw new Error("INVALID_PEOPLE_RESPONSE");
      if (payload.length === 0) return null;
      if (!isPerson(payload[0])) throw new Error("INVALID_PEOPLE_RESPONSE");
      return payload[0];
    },

    async getTiming(personId: string, asOfDate: string): Promise<Timing> {
      const payload = await read(`/v1/people/${personId}/timing?as_of_date=${asOfDate}`);
      if (!isTiming(payload)) throw new Error("INVALID_TIMING_RESPONSE");
      return payload;
    },

    async getDailyBrief(personId: string, asOfDate: string): Promise<DailyBrief> {
      const payload = await read(`/v1/people/${personId}/daily-brief?as_of_date=${asOfDate}`);
      if (!isDailyBrief(payload)) throw new Error("INVALID_DAILY_BRIEF_RESPONSE");
      return payload;
    },
  };
}
