"use client";

import { AppShell } from "@/components/layout/app-shell";
import { LinkButton } from "@/components/ui/link-button";
import { Card, CardContent } from "@/components/ui/card";
import { LoadingState, ErrorState, EmptyState } from "@/components/ui/states";
import { api, type PersonOut } from "@/api/client";
import { useAsync } from "@/lib/use-async";
import { formatIsoDate } from "@/lib/utils";
import { UserPlus } from "lucide-react";

function personLabel(person: PersonOut): string {
  const preferred = person.preferred_name?.trim();
  if (preferred) return preferred;
  return `${person.birth_first_names} ${person.birth_last_name}`.trim();
}

function PeopleContent() {
  const peopleState = useAsync(() => api.people.list(), []);

  return (
    <div>
      <div className="mb-8 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="font-serif text-3xl text-ivory">People</h1>
          <p className="mt-1 text-sm text-muted">Every profile you have created.</p>
        </div>
        <LinkButton href="/people/new">
          <UserPlus className="h-4 w-4" aria-hidden="true" />
          New profile
        </LinkButton>
      </div>

      {peopleState.status === "loading" && <LoadingState label="Loading people…" />}
      {peopleState.status === "error" && (
        <ErrorState error={peopleState.error} onRetry={peopleState.reload} />
      )}
      {peopleState.status === "success" && peopleState.data.length === 0 && (
        <EmptyState
          title="No profiles yet"
          description="Create a profile with a birth name and date to run its first calculation."
          action={
            <LinkButton href="/people/new">
              <UserPlus className="h-4 w-4" aria-hidden="true" />
              New profile
            </LinkButton>
          }
        />
      )}
      {peopleState.status === "success" && peopleState.data.length > 0 && (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {peopleState.data.map((person) => (
            <Card key={person.id}>
              <CardContent>
                <p className="font-serif text-lg text-ivory">{personLabel(person)}</p>
                <p className="text-sm text-muted">Born {formatIsoDate(person.birth_date)}</p>
                <LinkButton
                  href={`/people/${person.id}`}
                  variant="secondary"
                  size="sm"
                  className="mt-4 w-full"
                >
                  Open profile
                </LinkButton>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}

export default function PeoplePage() {
  return (
    <AppShell>
      <PeopleContent />
    </AppShell>
  );
}
