import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { MetricBadges } from "@/components/analysis/metric-badges";
import type { CalculationMetric } from "@/api/canonical-profile";

function makeMetric(overrides: Partial<CalculationMetric>): CalculationMetric {
  return {
    metric_id: "life_path",
    system: "numra-canonical",
    method: "segmented_v1",
    source_value: null,
    raw_value: 22,
    root_value: 4,
    master_number: 22,
    effective_value: 22,
    display_value: "22/4",
    calculation_trace: { operations: [] },
    flags: [],
    ...overrides,
  };
}

describe("MetricBadges", () => {
  it("shows a Master Number badge when master_number is set", () => {
    render(<MetricBadges metric={makeMetric({})} />);
    expect(screen.getByText(/Master Number 22/i)).toBeInTheDocument();
  });

  it("shows a Karmic Debt badge from flags, distinct from Master Number", () => {
    const metric = makeMetric({
      master_number: null,
      effective_value: 13,
      display_value: "13/4",
      flags: [{ code: "KARMIC_DEBT", value: "13/4", source_raw_value: 13 }],
    });
    render(<MetricBadges metric={metric} />);
    expect(screen.getByText(/Karmic Debt 13\/4/i)).toBeInTheDocument();
    expect(screen.queryByText(/Master Number/i)).not.toBeInTheDocument();
  });

  it("renders nothing when there is nothing to flag", () => {
    const metric = makeMetric({ master_number: null, flags: [] });
    const { container } = render(<MetricBadges metric={metric} />);
    expect(container).toBeEmptyDOMElement();
  });
});
