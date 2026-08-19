import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import {
  RELATIONSHIP_METRIC_KEYS,
  type RelationshipComparison,
} from "@/api/canonical-profile";
import { Check, X } from "lucide-react";

const METRIC_LABELS: Record<string, string> = {
  life_path: "Life Path",
  expression: "Expression",
  soul_urge: "Soul Urge",
  personality: "Personality",
  maturity: "Maturity",
  personal_year: "Personal Year",
  personal_month: "Personal Month",
  personal_day: "Personal Day",
};

export function ComparisonTable({ comparison }: { comparison: RelationshipComparison }) {
  const rows = RELATIONSHIP_METRIC_KEYS.map((key) => ({ key, value: comparison[key] })).filter(
    (row) => row.value !== undefined,
  );

  if (rows.length === 0) {
    return (
      <p className="text-sm text-muted">
        This comparison did not include any of the expected metrics.
      </p>
    );
  }

  return (
    <Card>
      <CardContent className="overflow-x-auto p-0">
        <table className="w-full min-w-[520px] text-left text-sm">
          <caption className="sr-only">
            Metric-by-metric comparison between two profiles. Each row shows both display
            values and whether they match — no compatibility percentage is computed or shown.
          </caption>
          <thead>
            <tr className="border-b border-white/10 text-muted">
              <th scope="col" className="px-5 py-3 font-normal">Metric</th>
              <th scope="col" className="px-5 py-3 font-normal">Person A</th>
              <th scope="col" className="px-5 py-3 font-normal">Person B</th>
              <th scope="col" className="px-5 py-3 font-normal">Match</th>
            </tr>
          </thead>
          <tbody>
            {rows.map(({ key, value }) => (
              <tr key={key} className="border-b border-white/5 last:border-0">
                <td className="px-5 py-3 text-ivory">{METRIC_LABELS[key] ?? key}</td>
                <td className="px-5 py-3 font-mono text-text">{value?.person_a.display_value}</td>
                <td className="px-5 py-3 font-mono text-text">{value?.person_b.display_value}</td>
                <td className="px-5 py-3">
                  {value?.match ? (
                    <Badge variant="success">
                      <Check className="h-3 w-3" aria-hidden="true" /> Match
                    </Badge>
                  ) : (
                    <Badge variant="neutral">
                      <X className="h-3 w-3" aria-hidden="true" /> No match
                    </Badge>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </CardContent>
    </Card>
  );
}
