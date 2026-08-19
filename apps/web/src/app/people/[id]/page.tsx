"use client";

import { useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { AppShell } from "@/components/layout/app-shell";
import { Card, CardContent, CardHeader, CardTitle, CardFooter } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { LinkButton } from "@/components/ui/link-button";
import { LoadingState, ErrorState } from "@/components/ui/states";
import { api, ApiError } from "@/api/client";
import { useAsync } from "@/lib/use-async";
import { recordCalculation, getLatestForPerson } from "@/lib/local-calculations";
import { formatIsoDate, todayIsoDate } from "@/lib/utils";
import { Sparkles, Trash2 } from "lucide-react";

function PersonDetailContent({ personId }: { personId: string }) {
  const router = useRouter();
  const personState = useAsync(() => api.people.get(personId), [personId]);
  const [calcStage, setCalcStage] = useState<"idle" | "running" | "error">("idle");
  const [calcError, setCalcError] = useState<{ code: string; message: string } | null>(null);
  const [deleting, setDeleting] = useState(false);
  const cached = getLatestForPerson(personId);

  async function runCalculation() {
    setCalcStage("running");
    setCalcError(null);
    try {
      const asOfDate = todayIsoDate();
      const calculation = await api.calculations.create(personId, { as_of_date: asOfDate });
      if (personState.status === "success") {
        const p = personState.data;
        recordCalculation({
          calculationId: calculation.id,
          personId,
          personLabel: p.preferred_name || `${p.birth_first_names} ${p.birth_last_name}`,
          asOfDate,
        });
      }
      router.push(`/analysis/${calculation.id}`);
    } catch (err) {
      setCalcStage("error");
      setCalcError(
        err instanceof ApiError
          ? { code: err.code, message: err.message }
          : { code: "NETWORK_ERROR", message: "Could not reach the server." },
      );
    }
  }

  async function handleDelete() {
    if (!window.confirm("Delete this profile? This cannot be undone.")) return;
    setDeleting(true);
    try {
      await api.people.remove(personId);
      router.push("/people");
    } catch (err) {
      setDeleting(false);
      setCalcError(
        err instanceof ApiError
          ? { code: err.code, message: err.message }
          : { code: "NETWORK_ERROR", message: "Could not reach the server." },
      );
    }
  }

  if (personState.status === "loading") return <LoadingState label="Loading profile…" />;
  if (personState.status === "error") {
    return <ErrorState error={personState.error} onRetry={personState.reload} />;
  }

  const person = personState.data;
  const label = person.preferred_name || `${person.birth_first_names} ${person.birth_last_name}`;

  return (
    <div className="flex flex-col gap-6">
      <Card>
        <CardHeader>
          <CardTitle>{label}</CardTitle>
        </CardHeader>
        <CardContent>
          <dl className="grid gap-x-6 gap-y-3 text-sm sm:grid-cols-2">
            <div>
              <dt className="text-muted">Birth name</dt>
              <dd className="text-text">
                {[person.birth_first_names, person.birth_middle_names, person.birth_last_name]
                  .filter(Boolean)
                  .join(" ")}
              </dd>
            </div>
            <div>
              <dt className="text-muted">Birth date</dt>
              <dd className="text-text">{formatIsoDate(person.birth_date)}</dd>
            </div>
            <div>
              <dt className="text-muted">Birth time</dt>
              <dd className="text-text">
                {person.birth_time?.value ?? "—"}{" "}
                {person.birth_time && (
                  <span className="text-muted">({person.birth_time.precision})</span>
                )}
              </dd>
            </div>
            <div>
              <dt className="text-muted">Birth place</dt>
              <dd className="text-text">{person.birth_place?.display_name ?? "—"}</dd>
            </div>
            {(person.current_first_names || person.current_last_name) && (
              <div>
                <dt className="text-muted">Current name</dt>
                <dd className="text-text">
                  {[person.current_first_names, person.current_middle_names, person.current_last_name]
                    .filter(Boolean)
                    .join(" ")}
                </dd>
              </div>
            )}
          </dl>
        </CardContent>
        <CardFooter className="flex flex-wrap items-center gap-3">
          <Button onClick={runCalculation} loading={calcStage === "running"}>
            <Sparkles className="h-4 w-4" aria-hidden="true" />
            Run new calculation (as of today)
          </Button>
          {cached && (
            <LinkButton variant="secondary" href={`/analysis/${cached.calculationId}`}>
              View last analysis
            </LinkButton>
          )}
          <Button variant="danger" onClick={handleDelete} loading={deleting} className="ml-auto">
            <Trash2 className="h-4 w-4" aria-hidden="true" />
            Delete profile
          </Button>
        </CardFooter>
      </Card>

      {calcError && (
        <div role="alert" className="rounded-lg border border-danger/30 bg-danger-surface p-3 text-sm text-text">
          <span className="mr-1.5 rounded bg-black/20 px-1.5 py-0.5 font-mono text-xs">
            {calcError.code}
          </span>
          {calcError.message}
        </div>
      )}
    </div>
  );
}

export default function PersonDetailPage() {
  const params = useParams<{ id: string }>();
  return (
    <AppShell>
      <div className="mb-8">
        <h1 className="font-serif text-3xl text-ivory">Profile</h1>
      </div>
      <PersonDetailContent personId={params.id} />
    </AppShell>
  );
}
