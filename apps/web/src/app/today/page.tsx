"use client";

import { useEffect, useMemo, useState } from "react";
import { AppShell } from "@/components/layout/app-shell";
import { LoadingState, ErrorState, EmptyState } from "@/components/ui/states";
import { Select } from "@/components/ui/select";
import { LinkButton } from "@/components/ui/link-button";
import { TimingView } from "@/components/today/timing-view";
import { DailyBriefView } from "@/components/today/daily-brief-view";
import { api, type PersonOut } from "@/api/client";
import { asTiming } from "@/api/canonical-profile";
import { useAsync } from "@/lib/use-async";
import { personDisplayName } from "@/lib/identity";
import { getTodayPersonId, setTodayPersonId } from "@/lib/local-preferences";
import { todayIsoDate } from "@/lib/utils";
import { UserPlus } from "lucide-react";

function TodayForPerson({
  personId,
  personLabel,
  asOfDate,
}: {
  personId: string;
  personLabel: string;
  asOfDate: string;
}) {
  const timingState = useAsync(() => api.people.timing(personId, asOfDate), [personId, asOfDate]);

  if (timingState.status === "loading") return <LoadingState label="Reading today…" />;
  if (timingState.status === "error") {
    return (
      <ErrorState
        error={timingState.error}
        onRetry={timingState.reload}
        title="Could not read today's timing"
      />
    );
  }

  const timing = asTiming(timingState.data);
  if (!timing) {
    return (
      <ErrorState
        error={new Error("The timing payload did not match the expected shape.")}
        title="Unreadable timing"
        onRetry={timingState.reload}
      />
    );
  }

  return (
    <>
      <TimingView personLabel={personLabel} timing={timing} />
      <DailyBriefView personId={personId} asOfDate={asOfDate} />
    </>
  );
}

function TodayContent() {
  const peopleState = useAsync(() => api.people.list(), []);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const asOfDate = useMemo(() => todayIsoDate(), []);

  const people: PersonOut[] = peopleState.status === "success" ? peopleState.data : [];

  // Open straight into the person last viewed here, when they still exist; otherwise
  // the first profile. A remembered id is never trusted blindly — it is checked
  // against what the API actually returned.
  useEffect(() => {
    if (peopleState.status !== "success" || peopleState.data.length === 0) return;
    setSelectedId((current) => {
      if (current && peopleState.data.some((p) => p.id === current)) return current;
      const remembered = getTodayPersonId();
      if (remembered && peopleState.data.some((p) => p.id === remembered)) return remembered;
      return peopleState.data[0]?.id ?? null;
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [peopleState.status]);

  function handleSelect(personId: string) {
    setSelectedId(personId);
    setTodayPersonId(personId);
  }

  const selected = people.find((p) => p.id === selectedId) ?? null;

  return (
    <div>
      <div className="mb-8 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="font-serif text-3xl text-ivory">Today</h1>
          <p className="mt-1 text-sm text-muted">
            Where this date falls in a personal cycle — recomputed live, never guessed.
          </p>
        </div>
        {people.length > 1 && (
          <div className="w-full sm:w-64">
            <label htmlFor="today-person" className="mb-1.5 block text-xs text-muted">
              Whose day?
            </label>
            <Select
              id="today-person"
              value={selectedId ?? ""}
              onChange={(e) => handleSelect(e.target.value)}
            >
              {people.map((person) => (
                <option key={person.id} value={person.id}>
                  {personDisplayName(person)}
                </option>
              ))}
            </Select>
          </div>
        )}
      </div>

      {peopleState.status === "loading" && <LoadingState label="Loading your people…" />}
      {peopleState.status === "error" && (
        <ErrorState error={peopleState.error} onRetry={peopleState.reload} />
      )}
      {peopleState.status === "success" && people.length === 0 && (
        <EmptyState
          title="No profiles yet"
          description="Today needs a birth date to work from. Create a profile and this page becomes your daily view."
          action={
            <LinkButton href="/people/new">
              <UserPlus className="h-4 w-4" aria-hidden="true" />
              New profile
            </LinkButton>
          }
        />
      )}
      {selected && (
        <TodayForPerson
          personId={selected.id}
          personLabel={personDisplayName(selected)}
          asOfDate={asOfDate}
        />
      )}
    </div>
  );
}

export default function TodayPage() {
  return (
    <AppShell>
      <TodayContent />
    </AppShell>
  );
}
