"use client";

import { useMemo, useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { AppShell } from "@/components/layout/app-shell";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Button } from "@/components/ui/button";
import { LinkButton } from "@/components/ui/link-button";
import { EmptyState, LoadingState, ErrorState } from "@/components/ui/states";
import { api, ApiError, type PersonOut } from "@/api/client";
import { useAsync } from "@/lib/use-async";
import { personDisplayName } from "@/lib/identity";
import { formatDateTime } from "@/lib/utils";
import { GitCompareArrows, Sparkles } from "lucide-react";

function personOptionLabel(person: PersonOut): string {
  return personDisplayName(person);
}

/**
 * V1.5 Epic E: the user selects two *people*, never a pasted calculation UUID --
 * the backend resolves each person's latest calculation server-side
 * (POST /v1/relationships with person_a_id/person_b_id). A person with no
 * calculation yet gets a specific, actionable error instead of a raw 404.
 */
function ComparisonForm({ people }: { people: PersonOut[] }) {
  const router = useRouter();
  const [personAId, setPersonAId] = useState(people[0]?.id ?? "");
  const [personBId, setPersonBId] = useState(people[1]?.id ?? people[0]?.id ?? "");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<{ code: string; message: string; personId?: string } | null>(
    null,
  );

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const relationship = await api.relationships.create({
        person_a_id: personAId,
        person_b_id: personBId,
      });
      router.push(`/relationships/${relationship.id}`);
    } catch (err) {
      setSubmitting(false);
      if (err instanceof ApiError && err.status === 404) {
        // The route's NotFoundError message names which person lacks a calculation
        // -- surface a specific "run it first" prompt rather than a generic error.
        const missingPersonId = err.message.includes(personAId)
          ? personAId
          : err.message.includes(personBId)
            ? personBId
            : undefined;
        setError({
          code: err.code,
          message: "That profile has no calculation yet.",
          personId: missingPersonId,
        });
      } else {
        setError(
          err instanceof ApiError
            ? { code: err.code, message: err.message }
            : { code: "NETWORK_ERROR", message: "Could not reach the server." },
        );
      }
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Compare two profiles</CardTitle>
        <CardDescription>
          Numra compares each person&apos;s latest calculation. If someone has no calculation yet,
          run one first.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit}>
          <div className="grid gap-5 sm:grid-cols-2">
            <div>
              <Label htmlFor="personA">Person A</Label>
              <Select id="personA" value={personAId} onChange={(e) => setPersonAId(e.target.value)}>
                {people.map((p) => (
                  <option key={p.id} value={p.id}>
                    {personOptionLabel(p)}
                  </option>
                ))}
              </Select>
            </div>
            <div>
              <Label htmlFor="personB">Person B</Label>
              <Select id="personB" value={personBId} onChange={(e) => setPersonBId(e.target.value)}>
                {people.map((p) => (
                  <option key={p.id} value={p.id}>
                    {personOptionLabel(p)}
                  </option>
                ))}
              </Select>
            </div>
          </div>

          {error && (
            <div
              role="alert"
              className="mt-5 rounded-lg border border-danger/30 bg-danger-surface p-3 text-sm text-text"
            >
              <div>
                <span className="mr-1.5 rounded bg-black/20 px-1.5 py-0.5 font-mono text-xs">
                  {error.code}
                </span>
                {error.message}
              </div>
              {error.personId && (
                <LinkButton
                  size="sm"
                  variant="secondary"
                  href={`/people/${error.personId}`}
                  className="mt-3"
                >
                  <Sparkles className="h-3.5 w-3.5" aria-hidden="true" />
                  Open profile to run a calculation
                </LinkButton>
              )}
            </div>
          )}

          <Button
            type="submit"
            className="mt-5"
            loading={submitting}
            disabled={!personAId || !personBId || personAId === personBId}
          >
            <GitCompareArrows className="h-4 w-4" aria-hidden="true" />
            Compare
          </Button>
          {personAId && personAId === personBId && (
            <p className="mt-2 text-xs text-muted">Choose two different people.</p>
          )}
        </form>
      </CardContent>
    </Card>
  );
}

/**
 * Server-authoritative — a fresh browser context with no LocalStorage still sees
 * every comparison this account has ever created (V1.5 Epic A/E), with real person
 * names resolved by the API, not a browser-only cache.
 */
function RecentComparisons() {
  const state = useAsync(() => api.relationships.list(), []);

  if (state.status === "loading") return <LoadingState label="Loading comparisons…" />;
  if (state.status === "error") {
    return (
      <ErrorState
        error={state.error}
        onRetry={state.reload}
        title="Could not load your comparisons"
      />
    );
  }
  if (state.data.length === 0) return null;

  return (
    <div className="mt-8">
      <h2 className="mb-4 font-serif text-xl text-ivory">Recent comparisons</h2>
      <div className="grid gap-3 sm:grid-cols-2">
        {state.data.map((r) => (
          <Card key={r.id}>
            <CardContent className="flex items-center justify-between gap-3">
              <div>
                <p className="text-text">
                  {r.person_a.display_name} <span className="text-muted">vs.</span>{" "}
                  {r.person_b.display_name}
                </p>
                <p className="text-xs text-muted">{formatDateTime(r.created_at)}</p>
              </div>
              <LinkButton size="sm" variant="secondary" href={`/relationships/${r.id}`}>
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
  const peopleState = useAsync(() => api.people.list(), []);
  const people = useMemo(
    () => (peopleState.status === "success" ? peopleState.data : []),
    [peopleState],
  );

  return (
    <div>
      <div className="mb-8">
        <h1 className="font-serif text-3xl text-ivory">Relationships</h1>
        <p className="mt-1 text-sm text-muted">
          Compare two calculated profiles, metric by metric.
        </p>
      </div>

      {peopleState.status === "loading" && <LoadingState label="Loading profiles…" />}
      {peopleState.status === "error" && (
        <ErrorState error={peopleState.error} onRetry={peopleState.reload} />
      )}
      {peopleState.status === "success" && people.length < 2 && (
        <div className="mb-6">
          <EmptyState
            title="Add a second profile to compare"
            description="Numra needs at least two people, each with a calculation, before it can compare them."
            action={
              <LinkButton href="/people/new" size="sm">
                New profile
              </LinkButton>
            }
          />
        </div>
      )}
      {peopleState.status === "success" && people.length >= 2 && <ComparisonForm people={people} />}

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
