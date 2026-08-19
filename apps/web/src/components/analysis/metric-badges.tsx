import { Badge } from "@/components/ui/badge";
import type { CalculationMetric } from "@/api/canonical-profile";

export function MetricBadges({ metric }: { metric: CalculationMetric }) {
  const karmicFlag = metric.flags.find((f) => f.code === "KARMIC_DEBT");
  const noVowels = metric.flags.find((f) => f.code === "NO_VOWELS");

  if (!metric.master_number && !karmicFlag && !noVowels) return null;

  return (
    <div className="flex flex-wrap gap-1.5">
      {metric.master_number !== null && (
        <Badge variant="master" title={`Master Number ${metric.master_number}`}>
          Master Number {metric.master_number}
        </Badge>
      )}
      {karmicFlag && (
        <Badge variant="karmic" title={`Karmic Debt ${karmicFlag.value ?? ""}`}>
          Karmic Debt {karmicFlag.value}
        </Badge>
      )}
      {noVowels && <Badge variant="neutral">No vowels in name</Badge>}
    </div>
  );
}
