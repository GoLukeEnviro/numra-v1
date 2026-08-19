/**
 * Frontend-side type model for `CalculationOut.canonical_profile`.
 *
 * The generated OpenAPI schema (packages/schema/src/generated/schema.d.ts) types
 * `canonical_profile` as `{ [key: string]: unknown }` because the FastAPI backend
 * declares it as an open JSON object (see openapi/numra-v1.json). The actual shape
 * is fully specified in specs/canon-spec.md §34-35 and pinned by
 * fixtures/canonical/lukas-springer.v1.json — this module mirrors that contract on
 * the client so the rest of the app can work with typed data instead of `unknown`.
 *
 * This is a type + light structural guard, not a re-implementation of validation:
 * the backend is the source of truth for correctness. `isCanonicalProfile` only
 * checks that the top-level shape described in canon-spec.md §35 is present so the
 * UI can fail safely (render an error state) instead of throwing on unexpected data.
 */

export interface MetricFlag {
  code: string;
  value?: string | null;
  source_raw_value?: number | null;
}

export interface ReductionResult {
  source_value: number | string | null;
  raw_value: number;
  root_value: number;
  master_number: number | null;
  effective_value: number;
  display_value: string;
  reduction_steps: number[];
}

/** One step in a `CalculationTrace.operations` list. Shape varies by `type`. */
export interface TraceOperation {
  type: string;
  [key: string]: unknown;
}

export interface CalculationTrace {
  input_refs?: string[];
  normalization?: Record<string, unknown>;
  operations: TraceOperation[];
}

export interface CalculationMetric {
  metric_id: string;
  system: string;
  method: string;
  source_value: number | string | null;
  raw_value: number;
  root_value: number;
  master_number: number | null;
  effective_value: number;
  display_value: string;
  calculation_trace: CalculationTrace;
  flags: MetricFlag[];
}

export interface HiddenPassion {
  values: number[];
  frequency: number;
  calculation_trace: CalculationTrace;
}

export interface KarmicLessons {
  values: number[];
  calculation_trace: CalculationTrace;
}

export interface SubconsciousSelf {
  value: number;
  calculation_trace: CalculationTrace;
}

export interface LetterValue {
  letter: string;
  value: number;
}

export type IntensityTable = Record<string, number>;

export interface CoreNumbers {
  life_path: CalculationMetric;
  birthday: CalculationMetric;
  attitude: CalculationMetric;
  expression: CalculationMetric;
  soul_urge: CalculationMetric;
  personality: CalculationMetric;
  maturity: CalculationMetric;
  balance: CalculationMetric;
  hidden_passion: HiddenPassion;
  karmic_lessons: KarmicLessons;
  subconscious_self: SubconsciousSelf;
  cornerstone: LetterValue;
  capstone: LetterValue;
  first_vowel: LetterValue | null;
  intensity_table: IntensityTable;
}

export interface PeriodCycles {
  period_1: ReductionResult;
  period_2: ReductionResult;
  period_3: ReductionResult;
}

export interface PinnacleWindow {
  start_date: string;
  end_date: string | null;
  start_age: number;
  end_age: number | null;
}

export interface Pinnacles {
  pinnacle_1: ReductionResult;
  pinnacle_2: ReductionResult;
  pinnacle_3: ReductionResult;
  pinnacle_4: ReductionResult;
  windows: PinnacleWindow[];
}

export interface Challenges {
  challenge_1: number;
  challenge_2: number;
  challenge_3: number;
  challenge_4: number;
}

export interface Cycles {
  period_cycles: PeriodCycles;
  pinnacles: Pinnacles;
  challenges: Challenges;
}

export interface Timing {
  as_of_date: string;
  universal_year: ReductionResult;
  personal_year: CalculationMetric;
  personal_month: CalculationMetric;
  personal_day: CalculationMetric;
}

export interface DiagnosticAlternative extends ReductionResult {
  method?: string;
  formula?: string;
  operands?: number[];
}

export interface Diagnostics {
  life_path?: {
    alternative_methods: {
      direct_digit_sum: DiagnosticAlternative;
    };
  };
  pinnacles?: {
    alternative_methods: Record<string, DiagnosticAlternative>;
  };
  [key: string]: unknown;
}

export interface CanonicalPerson {
  birth_first_names: string;
  birth_middle_names?: string | null;
  birth_last_name: string;
  birth_date: string;
  birth_time?: { value: string | null; precision: string } | null;
  birth_place?: { display_name: string; country_code?: string | null } | null;
}

export interface Normalization {
  original: string;
  components: string[];
  calculation_string: string;
}

export interface CanonicalProfile {
  schema_version: string;
  calculation_system: string;
  calculation_version: string;
  person: CanonicalPerson;
  normalization: Normalization;
  core_numbers: CoreNumbers;
  cycles: Cycles;
  timing: Timing;
  diagnostics: Diagnostics;
  warnings: unknown[];
}

/**
 * Structural guard for the top-level shape (canon-spec.md §35). Deliberately
 * shallow — it protects the UI from a completely malformed payload, it does not
 * re-validate the engine's math (that is the backend/engine's job, per the
 * determinism contract).
 */
export function isCanonicalProfile(value: unknown): value is CanonicalProfile {
  if (typeof value !== "object" || value === null) return false;
  const v = value as Record<string, unknown>;
  return (
    typeof v.schema_version === "string" &&
    typeof v.core_numbers === "object" &&
    v.core_numbers !== null &&
    typeof v.cycles === "object" &&
    v.cycles !== null &&
    typeof v.timing === "object" &&
    v.timing !== null &&
    typeof v.normalization === "object" &&
    v.normalization !== null
  );
}

export function asCanonicalProfile(value: unknown): CanonicalProfile | null {
  return isCanonicalProfile(value) ? value : null;
}

function hasDisplayValue(value: unknown): boolean {
  return (
    typeof value === "object" &&
    value !== null &&
    typeof (value as { display_value?: unknown }).display_value === "string"
  );
}

/**
 * Structural guard for `GET /v1/people/{id}/timing`, which returns exactly the
 * `timing` sub-object of a Canonical Profile (routes/calculations.py). Shallow by
 * design, mirroring `isCanonicalProfile`: it only confirms the four values the
 * Today view renders are present and carry a `display_value`, so a malformed
 * payload produces an error state instead of a blank or, worse, a made-up number.
 */
export function asTiming(value: unknown): Timing | null {
  if (typeof value !== "object" || value === null) return null;
  const v = value as Record<string, unknown>;
  const ok =
    typeof v.as_of_date === "string" &&
    hasDisplayValue(v.universal_year) &&
    hasDisplayValue(v.personal_year) &&
    hasDisplayValue(v.personal_month) &&
    hasDisplayValue(v.personal_day);
  return ok ? (value as Timing) : null;
}

/** Relationship comparison shape (RelationshipOut.comparison, openapi: additionalProperties). */
export interface RelationshipMetricComparison {
  person_a: { display_value: string };
  person_b: { display_value: string };
  match: boolean;
}

export const RELATIONSHIP_METRIC_KEYS = [
  "life_path",
  "expression",
  "soul_urge",
  "personality",
  "maturity",
  "personal_year",
  "personal_month",
  "personal_day",
] as const;

export type RelationshipMetricKey = (typeof RELATIONSHIP_METRIC_KEYS)[number];

export type RelationshipComparison = Partial<
  Record<RelationshipMetricKey, RelationshipMetricComparison>
>;

export function asRelationshipComparison(value: unknown): RelationshipComparison {
  if (typeof value !== "object" || value === null) return {};
  return value as RelationshipComparison;
}
