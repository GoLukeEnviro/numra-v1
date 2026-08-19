"use client";

import { useId, useState } from "react";
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
  personal_year: "Personal Year",
  personal_month: "Personal Month",
  personal_day: "Personal Day",
};

/**
 * One canonical metric.
 *
 * `display_value` is rendered as its own bare text node, deliberately: it is the
 * authoritative, already-master-formatted value from the engine (e.g. "22/4"), and
 * splitting or reformatting it here would be a second, unaudited representation of
 * the same number. The expandable trace below it is likewise only a rendering of
 * `calculation_trace` — nothing is recomputed in the browser.
 */
export function MetricCard({ metric }: { metric: CalculationMetric }) {
  const [open, setOpen] = useState(false);
  const panelId = useId();
  const label = METRIC_LABELS[metric.metric_id] ?? metric.metric_id;
  const isMaster = metric.master_number !== null;

  return (
    <Card
      className={cn(
        "group transition-colors",
        isMaster ? "border-gold/25 hover:border-gold/50" : "hover:border-white/20",
      )}
    >
      <CardContent className="flex h-full flex-col p-5">
        <p className="text-xs uppercase tracking-wider text-muted">{label}</p>

        <p className="mt-2 font-serif text-4xl leading-none text-gold">{metric.display_value}</p>

        <div className="mt-3 min-h-[1.5rem]">
          <MetricBadges metric={metric} />
        </div>

        <div className="mt-auto pt-4">
          <button
            type="button"
            onClick={() => setOpen((o) => !o)}
            aria-expanded={open}
            aria-controls={panelId}
            className="flex items-center gap-1 text-xs font-medium text-muted transition-colors hover:text-gold"
          >
            <ChevronDown
              className={cn("h-3.5 w-3.5 transition-transform", open && "rotate-180")}
              aria-hidden="true"
            />
            {open ? "Hide calculation trace" : "Show calculation trace"}
          </button>
          <div id={panelId} hidden={!open}>
            {open && (
              <div className="mt-3 border-t border-white/10 pt-3">
                <TraceList steps={renderTrace(metric)} />
              </div>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
