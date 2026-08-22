import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import {
  RELATIONSHIP_METRIC_KEYS,
  type RelationshipComparison,
  type RelationshipMetricComparison,
  type RelationshipMetricKey,
} from "@/api/canonical-profile";
import { cn } from "@/lib/utils";
import { Check, Minus } from "lucide-react";

export const METRIC_LABELS: Record<RelationshipMetricKey, string> = {
  life_path: "Life Path",
  expression: "Expression",
  soul_urge: "Soul Urge",
  personality: "Personality",
  maturity: "Maturity",
  personal_year: "Personal Year",
  personal_month: "Personal Month",
  personal_day: "Personal Day",
};

interface MetricGroup {
  id: string;
  title: string;
  description: string;
  keys: readonly RelationshipMetricKey[];
}

/**
 * Grouping is presentational only: it changes which heading a row sits under, never
 * which rows exist or what they say. The two groups mirror how the canonical profile
 * is organised — metrics derived from the birth name and birth date, and metrics that
 * depend on a calculation's as-of date.
 */
const METRIC_GROUPS: readonly MetricGroup[] = [
  {
    id: "core",
    title: "Core numbers",
    description: "Derived from each person's birth name and birth date. These do not change.",
    keys: ["life_path", "expression", "soul_urge", "personality", "maturity"],
  },
  {
    id: "timing",
    title: "Timing",
    description:
      "Derived from each calculation's as-of date — meaningful to compare only when both calculations share that date.",
    keys: ["personal_year", "personal_month", "personal_day"],
  },
] as const;

// Compile-time guarantee that every known metric key is placed in exactly one group:
// if a key is added to RELATIONSHIP_METRIC_KEYS without being grouped here, this
// mapping stops type-checking rather than silently dropping the metric from the UI.
type GroupedKeys = (typeof METRIC_GROUPS)[number]["keys"][number];
const GROUP_COVERAGE: Record<RelationshipMetricKey, GroupedKeys> = {
  life_path: "life_path",
  expression: "expression",
  soul_urge: "soul_urge",
  personality: "personality",
  maturity: "maturity",
  personal_year: "personal_year",
  personal_month: "personal_month",
  personal_day: "personal_day",
};

function MatchMarker({ match }: { match: boolean }) {
  return (
    <span
      className={cn(
        "inline-flex h-7 w-7 items-center justify-center rounded-full border",
        match ? "border-gold/50 bg-gold/15 text-gold" : "border-white/10 bg-surface-2 text-muted",
      )}
    >
      {match ? (
        <Check className="h-3.5 w-3.5" aria-hidden="true" />
      ) : (
        <Minus className="h-3.5 w-3.5" aria-hidden="true" />
      )}
      <span className="sr-only">{match ? "Same value" : "Different values"}</span>
    </span>
  );
}

function GroupTable({
  group,
  comparison,
  labelA,
  labelB,
}: {
  group: MetricGroup;
  comparison: RelationshipComparison;
  labelA: string;
  labelB: string;
}) {
  const rows: { key: RelationshipMetricKey; value: RelationshipMetricComparison }[] = [];
  for (const key of group.keys) {
    const value = comparison[key];
    if (value !== undefined) rows.push({ key, value });
  }

  if (rows.length === 0) return null;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">{group.title}</CardTitle>
        <CardDescription>{group.description}</CardDescription>
      </CardHeader>
      <CardContent className="overflow-x-auto p-0">
        <table className="w-full min-w-[520px] text-left text-sm">
          <caption className="sr-only">
            {group.title}: each row shows both people&apos;s values for one metric and whether
            they are the same. No compatibility percentage or overall score is computed
            anywhere in Numra.
          </caption>
          <thead>
            <tr className="border-b border-white/10 text-xs uppercase tracking-wider text-muted">
              <th scope="col" className="px-5 py-3 font-normal">
                Metric
              </th>
              <th scope="col" className="px-5 py-3 text-right font-normal">
                {labelA}
              </th>
              <th scope="col" className="w-16 px-2 py-3 text-center font-normal">
                <span className="sr-only">Same value</span>
              </th>
              <th scope="col" className="px-5 py-3 font-normal">
                {labelB}
              </th>
            </tr>
          </thead>
          <tbody>
            {rows.map(({ key, value }) => (
              <tr
                key={key}
                className={cn(
                  "border-b border-white/5 last:border-0",
                  value.match && "bg-gold/[0.04]",
                )}
              >
                <th scope="row" className="px-5 py-4 font-normal text-ivory">
                  {METRIC_LABELS[key]}
                </th>
                <td className="px-5 py-4 text-right">
                  <span
                    className={cn("font-serif text-2xl", value.match ? "text-gold" : "text-text")}
                  >
                    {value.person_a.display_value}
                  </span>
                </td>
                <td className="px-2 py-4 text-center">
                  <MatchMarker match={value.match} />
                </td>
                <td className="px-5 py-4">
                  <span
                    className={cn("font-serif text-2xl", value.match ? "text-gold" : "text-text")}
                  >
                    {value.person_b.display_value}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </CardContent>
    </Card>
  );
}

export function ComparisonTable({
  comparison,
  labelA = "Person A",
  labelB = "Person B",
}: {
  comparison: RelationshipComparison;
  labelA?: string;
  labelB?: string;
}) {
  void GROUP_COVERAGE;
  const hasAnyMetric = RELATIONSHIP_METRIC_KEYS.some((key) => comparison[key] !== undefined);

  if (!hasAnyMetric) {
    return (
      <p className="text-sm text-muted">
        This comparison did not include any of the expected metrics.
      </p>
    );
  }

  return (
    <div className="flex flex-col gap-6">
      {METRIC_GROUPS.map((group) => (
        <GroupTable
          key={group.id}
          group={group}
          comparison={comparison}
          labelA={labelA}
          labelB={labelB}
        />
      ))}
    </div>
  );
}
