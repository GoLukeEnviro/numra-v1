"use client";

import { AppShell } from "@/components/layout/app-shell";
import { api, type PersonOut } from "@/api/client";
import { useAsync } from "@/lib/use-async";
import { LoadingState, ErrorState, EmptyState } from "@/components/ui/states";
import { Card, CardContent } from "@/components/ui/card";
import { LinkButton } from "@/components/ui/link-button";
import { getLatestForPerson } from "@/lib/local-calculations";
import { formatIsoDate } from "@/lib/utils";
import { ArrowRight, Sparkles, UserPlus } from "lucide-react";

function personLabel(person: PersonOut): string {
  const preferred = person.preferred_name?.trim();
  if (preferred) return preferred;
  return `${person.birth_first_names} ${person.birth_last_name}`.trim();
}

function PersonRow({ person }: { person: PersonOut }) {
  const cached = getLatestForPerson(person.id);

  return (
    <Card>
      <CardContent className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="font-serif text-lg text-ivory">{personLabel(person)}</p>
          <p className="text-sm text-muted">Born {formatIsoDate(person.birth_date)}</p>
          {cached && (
            <p className="mt-1 text-xs text-muted">
              Last analysis as of {formatIsoDate(cached.asOfDate)}
            </p>
          )}
        </div>
        <div className="flex gap-2">
          {cached ? (
            <LinkButton variant="secondary" size="sm" href={`/analysis/${cached.calculationId}`}>
              View analysis <ArrowRight className="h-4 w-4" aria-hidden="true" />
            </LinkButton>
          ) : (
            <LinkButton size="sm" href={`/people/${person.id}`}>
              <Sparkles className="h-4 w-4" aria-hidden="true" />
              Run calculation
            </LinkButton>
          )}
          <LinkButton variant="ghost" size="sm" href={`/people/${person.id}`}>
            Profile
          </LinkButton>
        </div>
      </CardContent>
    </Card>
  );
}

function DashboardContent() {
  const peopleState = useAsync(() => api.people.list(), []);

  return (
    <div>
      <div className="mb-8 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="font-serif text-3xl text-ivory">Dashboard</h1>
          <p className="mt-1 text-sm text-muted">Your people and their latest analyses.</p>
        </div>
        <LinkButton href="/people/new">
          <UserPlus className="h-4 w-4" aria-hidden="true" />
          New profile
        </LinkButton>
      </div>

      {peopleState.status === "loading" && <LoadingState label="Loading your people…" />}
      {peopleState.status === "error" && (
        <ErrorState error={peopleState.error} onRetry={peopleState.reload} />
      )}
      {peopleState.status === "success" && peopleState.data.length === 0 && (
        <EmptyState
          title="No profiles yet"
          description="Create your first profile to run a deterministic numerology calculation."
          action={
            <LinkButton href="/people/new">
              <UserPlus className="h-4 w-4" aria-hidden="true" />
              New profile
            </LinkButton>
          }
        />
      )}
      {peopleState.status === "success" && peopleState.data.length > 0 && (
        <div className="flex flex-col gap-3">
          {peopleState.data.map((person) => (
            <PersonRow key={person.id} person={person} />
          ))}
        </div>
      )}
    </div>
  );
}

export default function DashboardPage() {
  return (
    <AppShell>
      <DashboardContent />
    </AppShell>
  );
}
