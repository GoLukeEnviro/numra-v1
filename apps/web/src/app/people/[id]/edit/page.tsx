"use client";

import { useEffect, useState, type FormEvent } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { AppShell } from "@/components/layout/app-shell";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Button } from "@/components/ui/button";
import { LoadingState, ErrorState } from "@/components/ui/states";
import { api, ApiError, type BirthTimePrecision, type PersonOut } from "@/api/client";
import { useAsync } from "@/lib/use-async";
import { todayIsoDate } from "@/lib/utils";
import { ArrowLeft, TriangleAlert } from "lucide-react";

interface FormState {
  birthFirstNames: string;
  birthMiddleNames: string;
  birthLastName: string;
  birthDate: string;
  birthTimeValue: string;
  birthTimePrecision: BirthTimePrecision;
  birthPlaceDisplayName: string;
  birthPlaceCountryCode: string;
  currentFirstNames: string;
  currentMiddleNames: string;
  currentLastName: string;
  preferredName: string;
}

function formFromPerson(person: PersonOut): FormState {
  return {
    birthFirstNames: person.birth_first_names,
    birthMiddleNames: person.birth_middle_names ?? "",
    birthLastName: person.birth_last_name,
    birthDate: person.birth_date,
    birthTimeValue: person.birth_time?.value?.slice(0, 5) ?? "",
    birthTimePrecision: person.birth_time?.precision ?? "unknown",
    birthPlaceDisplayName: person.birth_place?.display_name ?? "",
    birthPlaceCountryCode: person.birth_place?.country_code ?? "",
    currentFirstNames: person.current_first_names ?? "",
    currentMiddleNames: person.current_middle_names ?? "",
    currentLastName: person.current_last_name ?? "",
    preferredName: person.preferred_name ?? "",
  };
}

/** Fields the deterministic engine actually reads — an edit here means every *new*
 *  calculation reflects it, but every already-computed Calculation snapshot stays
 *  exactly as it was (see `apps/api/.../repositories/calculations.py`'s own
 *  docstring: a Calculation is never mutated after creation). */
const CANON_SENSITIVE_FIELDS: (keyof FormState)[] = [
  "birthFirstNames",
  "birthMiddleNames",
  "birthLastName",
  "birthDate",
];

function EditPersonForm({ person }: { person: PersonOut }) {
  const router = useRouter();
  const [form, setForm] = useState<FormState>(() => formFromPerson(person));
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<{ code: string; message: string } | null>(null);

  useEffect(() => setForm(formFromPerson(person)), [person]);

  function update<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  const original = formFromPerson(person);
  const canonSensitiveChanged = CANON_SENSITIVE_FIELDS.some((key) => form[key] !== original[key]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const birthTime =
        form.birthTimeValue.trim() || form.birthTimePrecision !== "unknown"
          ? {
              value: form.birthTimeValue.trim() ? `${form.birthTimeValue}:00` : null,
              precision: form.birthTimePrecision,
            }
          : null;
      const birthPlace = form.birthPlaceDisplayName.trim()
        ? {
            display_name: form.birthPlaceDisplayName.trim(),
            country_code: form.birthPlaceCountryCode.trim() || null,
          }
        : null;

      await api.people.patch(person.id, {
        birth_first_names: form.birthFirstNames.trim(),
        birth_middle_names: form.birthMiddleNames.trim() || null,
        birth_last_name: form.birthLastName.trim(),
        birth_date: form.birthDate,
        birth_time: birthTime,
        birth_place: birthPlace,
        current_first_names: form.currentFirstNames.trim() || null,
        current_middle_names: form.currentMiddleNames.trim() || null,
        current_last_name: form.currentLastName.trim() || null,
        preferred_name: form.preferredName.trim() || null,
      });
      router.push(`/people/${person.id}`);
    } catch (err) {
      setSubmitting(false);
      setError(
        err instanceof ApiError
          ? { code: err.code, message: err.message }
          : { code: "NETWORK_ERROR", message: "Could not reach the server." },
      );
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Edit profile</CardTitle>
        <CardDescription>
          The birth name and birth date drive every Core Number. Editing them here never changes
          a calculation you have already run.
        </CardDescription>
      </CardHeader>
      <CardContent>
        {canonSensitiveChanged && (
          <div
            role="note"
            className="mb-6 flex items-start gap-3 rounded-lg border border-gold/30 bg-gold/[0.06] p-4 text-sm text-text"
          >
            <TriangleAlert className="mt-0.5 h-4 w-4 shrink-0 text-gold" aria-hidden="true" />
            <p>
              Existing calculations remain unchanged. Only a new calculation you run after saving
              will use this updated birth data.
            </p>
          </div>
        )}

        <form onSubmit={handleSubmit} noValidate>
          <fieldset className="mb-6" disabled={submitting}>
            <legend className="mb-3 font-serif text-base text-ivory">Birth name</legend>
            <div className="grid gap-4 sm:grid-cols-2">
              <div>
                <Label htmlFor="birthFirstNames">First name(s) *</Label>
                <Input
                  id="birthFirstNames"
                  required
                  value={form.birthFirstNames}
                  onChange={(e) => update("birthFirstNames", e.target.value)}
                />
              </div>
              <div>
                <Label htmlFor="birthLastName">Last name *</Label>
                <Input
                  id="birthLastName"
                  required
                  value={form.birthLastName}
                  onChange={(e) => update("birthLastName", e.target.value)}
                />
              </div>
              <div className="sm:col-span-2">
                <Label htmlFor="birthMiddleNames">Middle name(s)</Label>
                <Input
                  id="birthMiddleNames"
                  value={form.birthMiddleNames}
                  onChange={(e) => update("birthMiddleNames", e.target.value)}
                />
              </div>
              <div>
                <Label htmlFor="birthDate">Birth date *</Label>
                <Input
                  id="birthDate"
                  type="date"
                  required
                  max={todayIsoDate()}
                  value={form.birthDate}
                  onChange={(e) => update("birthDate", e.target.value)}
                />
              </div>
            </div>
          </fieldset>

          <fieldset className="mb-6" disabled={submitting}>
            <legend className="mb-3 font-serif text-base text-ivory">
              Birth time &amp; place{" "}
              <span className="font-sans text-xs font-normal text-muted">
                (metadata only — never affects a Core Number)
              </span>
            </legend>
            <div className="grid gap-4 sm:grid-cols-2">
              <div>
                <Label htmlFor="birthTimeValue">Birth time</Label>
                <Input
                  id="birthTimeValue"
                  type="time"
                  value={form.birthTimeValue}
                  onChange={(e) => update("birthTimeValue", e.target.value)}
                />
              </div>
              <div>
                <Label htmlFor="birthTimePrecision">Time precision</Label>
                <Select
                  id="birthTimePrecision"
                  value={form.birthTimePrecision}
                  onChange={(e) =>
                    update("birthTimePrecision", e.target.value as BirthTimePrecision)
                  }
                >
                  <option value="exact">Exact</option>
                  <option value="approximate">Approximate</option>
                  <option value="unknown">Unknown</option>
                </Select>
              </div>
              <div>
                <Label htmlFor="birthPlaceDisplayName">Birth place</Label>
                <Input
                  id="birthPlaceDisplayName"
                  placeholder="e.g. Meerbusch"
                  value={form.birthPlaceDisplayName}
                  onChange={(e) => update("birthPlaceDisplayName", e.target.value)}
                />
              </div>
              <div>
                <Label htmlFor="birthPlaceCountryCode">Country code</Label>
                <Input
                  id="birthPlaceCountryCode"
                  placeholder="e.g. DE"
                  maxLength={2}
                  value={form.birthPlaceCountryCode}
                  onChange={(e) => update("birthPlaceCountryCode", e.target.value.toUpperCase())}
                />
              </div>
            </div>
          </fieldset>

          <fieldset className="mb-6" disabled={submitting}>
            <legend className="mb-3 font-serif text-base text-ivory">
              Current name &amp; preferred name{" "}
              <span className="font-sans text-xs font-normal text-muted">(optional)</span>
            </legend>
            <div className="grid gap-4 sm:grid-cols-2">
              <div>
                <Label htmlFor="currentFirstNames">Current first name(s)</Label>
                <Input
                  id="currentFirstNames"
                  value={form.currentFirstNames}
                  onChange={(e) => update("currentFirstNames", e.target.value)}
                />
              </div>
              <div>
                <Label htmlFor="currentLastName">Current last name</Label>
                <Input
                  id="currentLastName"
                  value={form.currentLastName}
                  onChange={(e) => update("currentLastName", e.target.value)}
                />
              </div>
              <div>
                <Label htmlFor="currentMiddleNames">Current middle name(s)</Label>
                <Input
                  id="currentMiddleNames"
                  value={form.currentMiddleNames}
                  onChange={(e) => update("currentMiddleNames", e.target.value)}
                />
              </div>
              <div>
                <Label htmlFor="preferredName">Preferred name</Label>
                <Input
                  id="preferredName"
                  value={form.preferredName}
                  onChange={(e) => update("preferredName", e.target.value)}
                />
              </div>
            </div>
          </fieldset>

          {error && (
            <div
              role="alert"
              className="mb-5 rounded-lg border border-danger/30 bg-danger-surface p-3 text-sm text-text"
            >
              <span className="mr-1.5 rounded bg-black/20 px-1.5 py-0.5 font-mono text-xs">
                {error.code}
              </span>
              {error.message}
            </div>
          )}

          <div className="flex gap-3">
            <Button type="submit" loading={submitting}>
              Save changes
            </Button>
            <Button type="button" variant="ghost" onClick={() => router.push(`/people/${person.id}`)}>
              Cancel
            </Button>
          </div>
        </form>
      </CardContent>
    </Card>
  );
}

function EditPersonContent({ personId }: { personId: string }) {
  const state = useAsync(() => api.people.get(personId), [personId]);

  if (state.status === "loading") return <LoadingState label="Loading profile…" />;
  if (state.status === "error") {
    return <ErrorState error={state.error} onRetry={state.reload} title="Could not load profile" />;
  }

  return (
    <div>
      <Link
        href={`/people/${personId}`}
        className="mb-6 inline-flex items-center gap-1.5 text-sm text-muted transition-colors hover:text-gold"
      >
        <ArrowLeft className="h-4 w-4" aria-hidden="true" />
        Back to profile
      </Link>
      <EditPersonForm person={state.data} />
    </div>
  );
}

export default function EditPersonPage() {
  const params = useParams<{ id: string }>();
  return (
    <AppShell>
      <EditPersonContent personId={params.id} />
    </AppShell>
  );
}
