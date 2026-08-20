"use client";

import Link from "next/link";
import { AppShell } from "@/components/layout/app-shell";
import { LinkButton } from "@/components/ui/link-button";
import { Badge } from "@/components/ui/badge";
import { LoadingState, ErrorState, EmptyState } from "@/components/ui/states";
import { api, type PersonOut } from "@/api/client";
import { useAsync } from "@/lib/use-async";
import { getLatestForPerson } from "@/lib/local-calculations";
import { personDisplayName } from "@/lib/identity";
import { formatIsoDate } from "@/lib/utils";
import { UserPlus, ArrowRight } from "lucide-react";

function PersonTile({ person }: { person: PersonOut }) {
  const cached = getLatestForPerson(person.id);
  const hasCurrentName = Boolean(
    person.current_first_names || person.current_middle_names || person.current_last_name,
  );

  return (
    <Link
      href={`/people/${person.id}`}
      className="group flex flex-col rounded-xl border border-white/10 bg-surface p-5 transition-colors hover:border-gold/40 hover:bg-surface-2"
    >
      <span className="flex-1">
        <span className="block font-serif text-xl text-ivory">{personDisplayName(person)}</span>
        <span className="mt-1 block text-sm text-muted">
          Born {formatIsoDate(person.birth_date)}
        </span>
      </span>

      <span className="mt-4 flex flex-wrap items-center gap-1.5">
        {hasCurrentName && <Badge variant="neutral">Current name recorded</Badge>}
        {person.preferred_name && <Badge variant="neutral">Preferred name</Badge>}
        {cached && <Badge variant="neutral">Analysed {formatIsoDate(cached.asOfDate)}</Badge>}
      </span>

      <span className="mt-4 inline-flex items-center gap-1 text-xs text-muted transition-colors group-hover:text-gold">
        Open profile <ArrowRight className="h-3 w-3" aria-hidden="true" />
      </span>
    </Link>
  );
}

function PeopleContent() {
  const peopleState = useAsync(() => api.people.list(), []);

  return (
    <div className="animate-rise-in">
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
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {peopleState.data.map((person) => (
            <PersonTile key={person.id} person={person} />
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
