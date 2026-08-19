import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import type { ReductionResult } from "@/api/canonical-profile";

export function ReductionResultCard({
  label,
  result,
}: {
  label: string;
  result: ReductionResult;
}) {
  return (
    <Card>
      <CardContent>
        <p className="text-sm text-muted">{label}</p>
        <p className="mt-1 font-serif text-2xl text-gold">{result.display_value}</p>
        {result.master_number !== null && (
          <div className="mt-2">
            <Badge variant="master">Master Number {result.master_number}</Badge>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
