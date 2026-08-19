"use client";

import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Select } from "@/components/ui/select";
import { Label } from "@/components/ui/label";
import { TraceList } from "@/components/analysis/trace-list";
import { MetricBadges } from "@/components/analysis/metric-badges";
import type { CoreNumbers, Diagnostics } from "@/api/canonical-profile";
import { renderTrace, renderDiagnostic } from "@/lib/trace";

type CoreMetricKey =
  | "life_path"
  | "birthday"
  | "attitude"
  | "expression"
  | "soul_urge"
  | "personality"
  | "maturity"
  | "balance";

const METRIC_OPTIONS: { id: CoreMetricKey; label: string }[] = [
  { id: "life_path", label: "Life Path" },
  { id: "birthday", label: "Birthday" },
  { id: "attitude", label: "Attitude" },
  { id: "expression", label: "Expression / Destiny" },
  { id: "soul_urge", label: "Soul Urge" },
  { id: "personality", label: "Personality" },
  { id: "maturity", label: "Maturity" },
  { id: "balance", label: "Balance" },
];

export function InspectorView({
  core,
  diagnostics,
}: {
  core: CoreNumbers;
  diagnostics: Diagnostics;
}) {
  const [selected, setSelected] = useState<CoreMetricKey>("life_path");
  const metric = core[selected];

  const directDigitSum = diagnostics.life_path?.alternative_methods.direct_digit_sum;

  return (
    <div className="flex flex-col gap-6">
      <div>
        <Label htmlFor="inspector-metric">Metric</Label>
        <div className="max-w-xs">
          <Select
            id="inspector-metric"
            value={selected}
            onChange={(e) => setSelected(e.target.value as CoreMetricKey)}
          >
            {METRIC_OPTIONS.map((opt) => (
              <option key={opt.id} value={opt.id}>
                {opt.label}
              </option>
            ))}
          </Select>
        </div>
      </div>

      <Card>
        <CardHeader>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <div className="mb-1 flex items-center gap-2">
                <Badge variant="success">Canonical</Badge>
                <CardTitle className="text-base">
                  {METRIC_OPTIONS.find((o) => o.id === selected)?.label} — {metric.method}
                </CardTitle>
              </div>
              <CardDescription>
                Result: <span className="font-mono text-gold">{metric.display_value}</span>
              </CardDescription>
            </div>
            <MetricBadges metric={metric} />
          </div>
        </CardHeader>
        <CardContent>
          <TraceList steps={renderTrace(metric)} />
        </CardContent>
      </Card>

      {selected === "life_path" && directDigitSum && (
        <Card className="border-dashed border-muted/40">
          <CardHeader>
            <div className="mb-1 flex items-center gap-2">
              <Badge variant="diagnostic">Diagnostic (non-canonical)</Badge>
              <CardTitle className="text-base">Life Path — Direct Digit Sum</CardTitle>
            </div>
            <CardDescription>
              canon-spec.md §9: concatenates every digit of the ISO birth date and sums
              directly, without per-segment reduction. Stored under{" "}
              <code className="font-mono text-xs">
                diagnostics.life_path.alternative_methods.direct_digit_sum
              </code>{" "}
              — this is never a second Life Path.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <TraceList steps={renderDiagnostic(directDigitSum)} />
          </CardContent>
        </Card>
      )}

      {diagnostics.pinnacles?.alternative_methods && (
        <Card className="border-dashed border-muted/40">
          <CardHeader>
            <div className="mb-1 flex items-center gap-2">
              <Badge variant="diagnostic">Diagnostic (non-canonical)</Badge>
              <CardTitle className="text-base">Pinnacles — historical formulas</CardTitle>
            </div>
            <CardDescription>
              canon-spec.md §24: historical diagnostic compounds, never canonical.
            </CardDescription>
          </CardHeader>
          <CardContent className="grid gap-3 sm:grid-cols-2">
            {Object.entries(diagnostics.pinnacles.alternative_methods).map(([key, alt]) => (
              <div key={key} className="rounded-lg border border-white/10 bg-surface-2 p-3">
                <p className="mb-1 text-xs text-muted">{key}</p>
                <p className="font-mono text-sm text-text">
                  {alt.formula ?? alt.method} → {alt.display_value}
                </p>
              </div>
            ))}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
