import type {
  CalculationMetric,
  DiagnosticAlternative,
  TraceOperation,
} from "@/api/canonical-profile";

export interface TraceStep {
  key: string;
  text: string;
}

function isSegmentPadded(segment: unknown): boolean {
  return segment === "month" || segment === "day";
}

/**
 * Renders a raw-value → ... → root chain the way canon-spec.md's worked
 * examples do (e.g. "18 → 9", "1986 → 24 → 6"), collapsing the duplicate first
 * step when the trace's first recorded step already equals the source value.
 */
function renderChain(sourceValue: number | string, steps: number[], pad: boolean): string {
  const sourceLabel = pad ? String(sourceValue).padStart(2, "0") : String(sourceValue);
  const sourceNum = Number(sourceValue);
  const rest = steps.length > 0 && steps[0] === sourceNum ? steps.slice(1) : steps;
  if (rest.length === 0) {
    const last = steps[steps.length - 1] ?? sourceValue;
    return `${sourceLabel} → ${last}`;
  }
  return `${sourceLabel} → ${rest.join(" → ")}`;
}

function num(v: unknown, fallback = 0): number {
  return typeof v === "number" ? v : fallback;
}

function numArray(v: unknown): number[] {
  return Array.isArray(v) ? v.filter((x): x is number => typeof x === "number") : [];
}

function renderOperation(op: TraceOperation, index: number): TraceStep {
  const key = `${op.type}-${index}`;
  switch (op.type) {
    case "segment_reduce": {
      const segment = String(op.segment ?? "");
      const source = (op.source_value as number | string | undefined) ?? "";
      const steps = numArray(op.steps);
      const chain = renderChain(source, steps, isSegmentPadded(segment));
      const label = segment ? `${segment[0]?.toUpperCase()}${segment.slice(1)}` : "Segment";
      return { key, text: `${label}: ${chain}` };
    }
    case "sum": {
      const operands = numArray(op.operands);
      const result = num(op.result);
      return { key, text: `${operands.join(" + ")} = ${result}` };
    }
    case "reduce": {
      const steps = numArray(op.steps);
      const operand = op.operand;
      if (typeof operand === "number" && steps.length > 0) {
        return { key, text: renderChain(operand, steps, false) };
      }
      if (steps.length > 1) {
        return { key, text: `→ ${steps.join(" → ")}` };
      }
      return { key, text: `→ ${steps[0] ?? ""}` };
    }
    case "letter_mapping": {
      const values = numArray(op.values);
      return { key, text: `Letter values: ${values.join(", ")}` };
    }
    case "frequency_count": {
      const table = (op.intensity_table ?? {}) as Record<string, number>;
      const parts = Object.entries(table).map(([k, v]) => `${k}×${v}`);
      return { key, text: `Frequency count: ${parts.join(", ")}` };
    }
    case "max_select": {
      const values = numArray(op.values);
      return {
        key,
        text: `Highest frequency ${num(op.max_frequency)} → values [${values.join(", ")}]`,
      };
    }
    case "missing_values": {
      const missing = numArray(op.missing);
      return { key, text: `Values with zero occurrences → [${missing.join(", ")}]` };
    }
    case "distinct_count": {
      const present = numArray(op.present_values);
      return {
        key,
        text: `Distinct values present [${present.join(", ")}] → count ${num(op.count)}`,
      };
    }
    default: {
      const { type: _type, ...rest } = op;
      return { key, text: `${op.type}: ${JSON.stringify(rest)}` };
    }
  }
}

/**
 * Turns a metric's `calculation_trace.operations` into an ordered, readable
 * list of steps, and appends a final "→ display_value" line so the chain
 * always ends at the metric's authoritative (and correctly master-formatted)
 * display value — never re-derived on the frontend, only re-stated from the
 * already-computed metric.
 */
export function renderTrace(metric: CalculationMetric): TraceStep[] {
  const ops = metric.calculation_trace?.operations ?? [];
  const steps = ops.map(renderOperation);
  steps.push({ key: "final", text: `→ ${metric.display_value}` });
  return steps;
}

export function renderOperations(ops: TraceOperation[]): TraceStep[] {
  return ops.map(renderOperation);
}

/**
 * Renders a `diagnostics.*.alternative_methods.*` entry (e.g. the Life Path
 * direct-digit-sum diagnostic, canon-spec.md §9). These are never presented as
 * a second canonical value — callers must label the surrounding UI
 * "Diagnostic (non-canonical)" themselves.
 */
export function renderDiagnostic(alt: DiagnosticAlternative): TraceStep[] {
  const steps: TraceStep[] = [];
  if (alt.operands && alt.operands.length > 0) {
    steps.push({ key: "operands", text: `${alt.operands.join(" + ")} = ${alt.raw_value}` });
  } else {
    steps.push({ key: "source", text: `source: ${String(alt.source_value)} = ${alt.raw_value}` });
  }
  if (alt.reduction_steps.length > 1) {
    steps.push({ key: "reduce", text: alt.reduction_steps.join(" → ") });
  }
  steps.push({ key: "final", text: `→ ${alt.display_value}` });
  return steps;
}
