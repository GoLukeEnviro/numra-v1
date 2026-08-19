import { Card, CardContent } from "@/components/ui/card";
import { MetricCard } from "@/components/analysis/metric-card";
import { IntensityTableView } from "@/components/analysis/intensity-table-view";
import type { CoreNumbers } from "@/api/canonical-profile";

const METRIC_ORDER = [
  "life_path",
  "birthday",
  "attitude",
  "expression",
  "soul_urge",
  "personality",
  "maturity",
  "balance",
] as const;

export function CoreNumbersView({ core }: { core: CoreNumbers }) {
  return (
    <div className="flex flex-col gap-8">
      <section>
        <h2 className="mb-4 font-serif text-xl text-ivory">Core Numbers</h2>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {METRIC_ORDER.map((id) => (
            <MetricCard key={id} metric={core[id]} />
          ))}
        </div>
      </section>

      <section>
        <h2 className="mb-4 font-serif text-xl text-ivory">Name analysis</h2>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <Card>
            <CardContent>
              <p className="text-sm text-muted">Hidden Passion</p>
              <p className="mt-1 font-serif text-2xl text-gold">
                {core.hidden_passion.values.join(", ")}
              </p>
              <p className="mt-1 text-xs text-muted">
                Frequency {core.hidden_passion.frequency}
              </p>
            </CardContent>
          </Card>
          <Card>
            <CardContent>
              <p className="text-sm text-muted">Karmic Lessons</p>
              <p className="mt-1 font-serif text-2xl text-gold">
                {core.karmic_lessons.values.length > 0
                  ? core.karmic_lessons.values.join(", ")
                  : "None"}
              </p>
            </CardContent>
          </Card>
          <Card>
            <CardContent>
              <p className="text-sm text-muted">Subconscious Self</p>
              <p className="mt-1 font-serif text-2xl text-gold">{core.subconscious_self.value}</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent>
              <p className="text-sm text-muted">Cornerstone</p>
              <p className="mt-1 font-serif text-2xl text-gold">
                {core.cornerstone.letter} <span className="text-base text-muted">({core.cornerstone.value})</span>
              </p>
            </CardContent>
          </Card>
          <Card>
            <CardContent>
              <p className="text-sm text-muted">Capstone</p>
              <p className="mt-1 font-serif text-2xl text-gold">
                {core.capstone.letter} <span className="text-base text-muted">({core.capstone.value})</span>
              </p>
            </CardContent>
          </Card>
          <Card>
            <CardContent>
              <p className="text-sm text-muted">First Vowel</p>
              <p className="mt-1 font-serif text-2xl text-gold">
                {core.first_vowel ? (
                  <>
                    {core.first_vowel.letter} <span className="text-base text-muted">({core.first_vowel.value})</span>
                  </>
                ) : (
                  <span className="text-base text-muted">None (no vowels in name)</span>
                )}
              </p>
            </CardContent>
          </Card>
        </div>
      </section>

      <section>
        <IntensityTableView table={core.intensity_table} />
      </section>
    </div>
  );
}
