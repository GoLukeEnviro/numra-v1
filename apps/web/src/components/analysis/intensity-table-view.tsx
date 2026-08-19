import { Card, CardContent } from "@/components/ui/card";
import type { IntensityTable } from "@/api/canonical-profile";

export function IntensityTableView({ table }: { table: IntensityTable }) {
  const entries = Array.from({ length: 9 }, (_, i) => String(i + 1)).map((k) => ({
    key: k,
    count: table[k] ?? 0,
  }));
  const max = Math.max(1, ...entries.map((e) => e.count));

  return (
    <Card>
      <CardContent>
        <p className="mb-4 text-sm text-muted">Intensity Table</p>
        <div className="flex items-end gap-2" role="img" aria-label="Letter-value frequency bars, 1 through 9">
          {entries.map((e) => (
            <div key={e.key} className="flex flex-1 flex-col items-center gap-1.5">
              <div className="flex h-24 w-full items-end justify-center">
                <div
                  className="w-full max-w-6 rounded-t bg-gold/70"
                  style={{ height: `${(e.count / max) * 100}%`, minHeight: e.count > 0 ? "4px" : "0" }}
                />
              </div>
              <span className="text-xs text-text">{e.key}</span>
              <span className="text-[10px] text-muted">{e.count}</span>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
