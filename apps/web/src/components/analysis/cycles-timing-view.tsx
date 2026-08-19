import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { MetricCard } from "@/components/analysis/metric-card";
import { ReductionResultCard } from "@/components/analysis/reduction-result-card";
import type { Cycles, Timing } from "@/api/canonical-profile";
import { formatIsoDate } from "@/lib/utils";

export function CyclesTimingView({ cycles, timing }: { cycles: Cycles; timing: Timing }) {
  return (
    <div className="flex flex-col gap-8">
      <section>
        <h2 className="mb-4 font-serif text-xl text-ivory">
          Timing <span className="text-sm font-sans font-normal text-muted">as of {formatIsoDate(timing.as_of_date)}</span>
        </h2>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <ReductionResultCard label="Universal Year" result={timing.universal_year} />
          <MetricCard metric={timing.personal_year} />
          <MetricCard metric={timing.personal_month} />
          <MetricCard metric={timing.personal_day} />
        </div>
      </section>

      <section>
        <h2 className="mb-4 font-serif text-xl text-ivory">Pinnacles</h2>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <ReductionResultCard label="Pinnacle 1" result={cycles.pinnacles.pinnacle_1} />
          <ReductionResultCard label="Pinnacle 2" result={cycles.pinnacles.pinnacle_2} />
          <ReductionResultCard label="Pinnacle 3" result={cycles.pinnacles.pinnacle_3} />
          <ReductionResultCard label="Pinnacle 4" result={cycles.pinnacles.pinnacle_4} />
        </div>
        <Card className="mt-4">
          <CardHeader>
            <CardTitle className="text-base">Age windows</CardTitle>
          </CardHeader>
          <CardContent className="overflow-x-auto p-0">
            <table className="w-full min-w-[480px] text-left text-sm">
              <thead>
                <tr className="border-b border-white/10 text-muted">
                  <th scope="col" className="px-5 py-3 font-normal">Pinnacle</th>
                  <th scope="col" className="px-5 py-3 font-normal">Ages</th>
                  <th scope="col" className="px-5 py-3 font-normal">Start date</th>
                  <th scope="col" className="px-5 py-3 font-normal">End date</th>
                </tr>
              </thead>
              <tbody>
                {cycles.pinnacles.windows.map((w, i) => (
                  <tr key={i} className="border-b border-white/5 last:border-0">
                    <td className="px-5 py-3 text-text">Pinnacle {i + 1}</td>
                    <td className="px-5 py-3 text-text">
                      {w.start_age}
                      {w.end_age !== null ? `–${w.end_age}` : "+"}
                    </td>
                    <td className="px-5 py-3 text-text">{formatIsoDate(w.start_date)}</td>
                    <td className="px-5 py-3 text-text">
                      {w.end_date ? formatIsoDate(w.end_date) : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </CardContent>
        </Card>
      </section>

      <section>
        <h2 className="mb-4 font-serif text-xl text-ivory">Challenges</h2>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {([1, 2, 3, 4] as const).map((n) => (
            <Card key={n}>
              <CardContent>
                <p className="text-sm text-muted">Challenge {n}</p>
                <p className="mt-1 font-serif text-2xl text-gold">
                  {cycles.challenges[`challenge_${n}` as keyof typeof cycles.challenges]}
                </p>
              </CardContent>
            </Card>
          ))}
        </div>
      </section>

      <section>
        <h2 className="mb-4 font-serif text-xl text-ivory">Period Cycles</h2>
        <div className="grid gap-4 sm:grid-cols-3">
          <ReductionResultCard label="Period 1 (month)" result={cycles.period_cycles.period_1} />
          <ReductionResultCard label="Period 2 (day)" result={cycles.period_cycles.period_2} />
          <ReductionResultCard label="Period 3 (year)" result={cycles.period_cycles.period_3} />
        </div>
      </section>
    </div>
  );
}
