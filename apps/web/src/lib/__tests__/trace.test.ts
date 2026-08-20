import { describe, expect, it } from "vitest";
import { renderTrace, renderDiagnostic } from "@/lib/trace";
import { asCanonicalProfile } from "@/api/canonical-profile";
import fixture from "@/fixtures/lukas-springer.v1.json";

// This exercises the trace renderer against the real golden fixture
// (fixtures/canonical/lukas-springer.v1.json, canon-spec.md §36) rather than a
// hand-rolled stub, so a change to the canonical trace shape breaks this test
// before it breaks the UI silently.
const profile = asCanonicalProfile(fixture);
if (!profile) throw new Error("fixture did not parse as a CanonicalProfile");

describe("renderTrace", () => {
  it("renders the Life Path segmented sum per canon-spec.md worked example", () => {
    const steps = renderTrace(profile.core_numbers.life_path).map((s) => s.text);
    expect(steps).toEqual([
      "Day: 18 → 9",
      "Month: 07 → 7",
      "Year: 1986 → 24 → 6",
      "9 + 7 + 6 = 22",
      "→ 22", // the metric's own final reduce op has a single step [22]
      "→ 22/4", // authoritative display_value, master-formatted
    ]);
  });

  it("renders the Birthday reduce chain", () => {
    const steps = renderTrace(profile.core_numbers.birthday).map((s) => s.text);
    expect(steps).toEqual(["18 → 9", "→ 18/9"]);
  });

  it("ends every trace with the metric's own authoritative display_value", () => {
    for (const metric of Object.values(profile.core_numbers).filter(
      (m): m is typeof profile.core_numbers.life_path =>
        typeof m === "object" && m !== null && "metric_id" in m,
    )) {
      const steps = renderTrace(metric);
      expect(steps[steps.length - 1]?.text).toBe(`→ ${metric.display_value}`);
    }
  });
});

describe("renderDiagnostic", () => {
  it("renders the Life Path direct-digit-sum diagnostic distinctly from the canonical trace", () => {
    const alt = profile.diagnostics.life_path?.alternative_methods.direct_digit_sum;
    expect(alt).toBeDefined();
    const steps = renderDiagnostic(alt!).map((s) => s.text);
    expect(steps).toEqual(["1 + 8 + 0 + 7 + 1 + 9 + 8 + 6 = 40", "40 → 4", "→ 40/4"]);
    // Canonical Life Path is 22/4 — the diagnostic must never collide with it.
    expect(alt!.display_value).not.toBe(profile.core_numbers.life_path.display_value);
  });

  it("does not crash when reduction_steps is absent (e.g. a pinnacle historical diagnostic)", () => {
    // cycles/pinnacles.py's pinnacle_1_historical/pinnacle_2_historical are
    // deliberately minimal dicts with no reduction_steps field at all — this must
    // render, not throw (a real system E2E run against the live engine's own output,
    // rather than the fixture above, is what caught this).
    expect(() =>
      renderDiagnostic({
        formula: "raw_month + raw_day",
        raw_value: 25,
        root_value: 7,
        display_value: "25/7",
      }),
    ).not.toThrow();
  });
});
