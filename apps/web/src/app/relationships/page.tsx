"use client";

import { useMemo, useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { AppShell } from "@/components/layout/app-shell";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Button } from "@/components/ui/button";
import { LinkButton } from "@/components/ui/link-button";
import { EmptyState } from "@/components/ui/states";
import { api, ApiError } from "@/api/client";
import { getAllCached } from "@/lib/local-calculations";
import { getAllCachedRelationships, recordRelationship } from "@/lib/local-relationships";
import { formatDateTime } from "@/lib/utils";
import { GitCompareArrows } from "lucide-react";

const MANUAL_OPTION = "__manual__";

function ComparisonForm() {
  const router = useRouter();
  const cachedCalculations = useMemo(() => getAllCached(), []);
  const [calcAChoice, setCalcAChoice] = useState(cachedCalculations[0]?.calculationId ?? MANUAL_OPTION);
  const [calcBChoice, setCalcBChoice] = useState(cachedCalculations[1]?.calculationId ?? MANUAL_OPTION);
  const [manualA, setManualA] = useState("");
  const [manualB, setManualB] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<{ code: string; message: string } | null>(null);

  const calculationAId = calcAChoice === MANUAL_OPTION ? manualA.trim() : calcAChoice;
  const calculationBId = calcBChoice === MANUAL_OPTION ? manualB.trim() : calcBChoice;

  function labelFor(id: string): string {
    const cached = cachedCalculations.find((c) => c.calculationId === id);
    return cached ? cached.personLabel : id.slice(0, 8);
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const relationship = await api.relationships.create({
        calculation_a_id: calculationAId,
        calculation_b_id: calculationBId,
      });
      recordRelationship({
        relationshipId: relationship.id,
        labelA: labelFor(calculationAId),
        labelB: labelFor(calculationBId),
      });
      router.push(`/relationships/${relationship.id}`);
    } catch (err) {
      setError(
        err instanceof ApiError
          ? { code: err.code, message: err.message }
          : { code: "NETWORK_ERROR", message: "Could not reach the server." },
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Compare two profiles</CardTitle>
        <CardDescription>
          Pick two calculations to compare. Recently viewed calculations from this browser are
          offered below — you can also paste a calculation ID directly (visible on any Analysis
          page).
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit}>
          <div className="grid gap-5 sm:grid-cols-2">
            <div>
              <Label htmlFor="calcA">Person A</Label>
              <Select id="calcA" value={calcAChoice} onChange={(e) => setCalcAChoice(e.target.value)}>
                {cachedCalculations.map((c) => (
                  <option key={c.calculationId} value={c.calculationId}>
                    {c.personLabel} — {c.calculationId.slice(0, 8)}
                  </option>
                ))}
                <option value={MANUAL_OPTION}>Paste calculation ID…</option>
              </Select>
              {calcAChoice === MANUAL_OPTION && (
                <Input
                  className="mt-2"
                  placeholder="Calculation ID"
                  value={manualA}
                  onChange={(e) => setManualA(e.target.value)}
                  aria-label="Calculation ID for person A"
                />
              )}
            </div>
            <div>
              <Label htmlFor="calcB">Person B</Label>
              <Select id="calcB" value={calcBChoice} onChange={(e) => setCalcBChoice(e.target.value)}>
                {cachedCalculations.map((c) => (
                  <option key={c.calculationId} value={c.calculationId}>
                    {c.personLabel} — {c.calculationId.slice(0, 8)}
                  </option>
                ))}
                <option value={MANUAL_OPTION}>Paste calculation ID…</option>
              </Select>
              {calcBChoice === MANUAL_OPTION && (
                <Input
                  className="mt-2"
                  placeholder="Calculation ID"
                  value={manualB}
                  onChange={(e) => setManualB(e.target.value)}
                  aria-label="Calculation ID for person B"
                />
              )}
            </div>
          </div>

          {error && (
            <div role="alert" className="mt-5 rounded-lg border border-danger/30 bg-danger-surface p-3 text-sm text-text">
              <span className="mr-1.5 rounded bg-black/20 px-1.5 py-0.5 font-mono text-xs">
                {error.code}
              </span>
              {error.message}
            </div>
          )}

          <Button
            type="submit"
            className="mt-5"
            loading={submitting}
            disabled={!calculationAId || !calculationBId}
          >
            <GitCompareArrows className="h-4 w-4" aria-hidden="true" />
            Compare
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}

function RecentComparisons() {
  const cached = useMemo(() => getAllCachedRelationships(), []);
  if (cached.length === 0) return null;

  return (
    <div className="mt-8">
      <h2 className="mb-4 font-serif text-xl text-ivory">Recent comparisons</h2>
      <div className="grid gap-3 sm:grid-cols-2">
        {cached.map((r) => (
          <Card key={r.relationshipId}>
            <CardContent className="flex items-center justify-between gap-3">
              <div>
                <p className="text-text">
                  {r.labelA} <span className="text-muted">vs.</span> {r.labelB}
                </p>
                <p className="text-xs text-muted">{formatDateTime(r.savedAt)}</p>
              </div>
              <LinkButton size="sm" variant="secondary" href={`/relationships/${r.relationshipId}`}>
                Open
              </LinkButton>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}

function RelationshipsContent() {
  const hasCachedCalculations = useMemo(() => getAllCached().length > 0, []);

  return (
    <div>
      <div className="mb-8">
        <h1 className="font-serif text-3xl text-ivory">Relationships</h1>
        <p className="mt-1 text-sm text-muted">
          Compare two calculated profiles, metric by metric.
        </p>
      </div>

      {!hasCachedCalculations && (
        <div className="mb-6">
          <EmptyState
            title="No calculations to compare yet"
            description="Run at least two calculations first — you can still paste calculation IDs manually below."
          />
        </div>
      )}

      <ComparisonForm />
      <RecentComparisons />
    </div>
  );
}

export default function RelationshipsPage() {
  return (
    <AppShell>
      <RelationshipsContent />
    </AppShell>
  );
}
