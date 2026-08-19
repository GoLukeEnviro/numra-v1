"use client";

import { useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { MetricBadges } from "@/components/analysis/metric-badges";
import { TraceList } from "@/components/analysis/trace-list";
import type { CalculationMetric } from "@/api/canonical-profile";
import { renderTrace } from "@/lib/trace";
import { ChevronDown } from "lucide-react";
import { cn } from "@/lib/utils";

const METRIC_LABELS: Record<string, string> = {
  life_path: "Life Path",
  birthday: "Birthday",
  attitude: "Attitude",
  expression: "Expression / Destiny",
  soul_urge: "Soul Urge",
  personality: "Personality",
  maturity: "Maturity",
  balance: "Balance",
};

export function MetricCard({ metric }: { metric: CalculationMetric }) {
  const [open, setOpen] = useState(false);
  const label = METRIC_LABELS[metric.metric_id] ?? metric.metric_id;

  return (
    <Card>
      <CardContent>
        <p className="text-sm text-muted">{label}</p>
        <p className="mt-1 font-serif text-3xl text-gold">{metric.display_value}</p>
        <div className="mt-3">
          <MetricBadges metric={metric} />
        </div>
        <button
          type="button"
          onClick={() => setOpen((o) => !o)}
          aria-expanded={open}
          className="mt-4 flex items-center gap-1 text-xs font-medium text-muted hover:text-gold"
        >
          <ChevronDown
            className={cn("h-3.5 w-3.5 transition-transform", open && "rotate-180")}
            aria-hidden="true"
          />
          {open ? "Hide calculation trace" : "Show calculation trace"}
        </button>
        {open && (
          <div className="mt-3 border-t border-white/10 pt-3">
            <TraceList steps={renderTrace(metric)} />
          </div>
        )}
      </CardContent>
    </Card>
  );
}
