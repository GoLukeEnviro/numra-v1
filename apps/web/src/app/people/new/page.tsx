"use client";

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { AppShell } from "@/components/layout/app-shell";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Button } from "@/components/ui/button";
import { api, ApiError, type BirthTimePrecision, type PersonInput } from "@/api/client";
import { recordCalculation } from "@/lib/local-calculations";
import { todayIsoDate } from "@/lib/utils";

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

const INITIAL_STATE: FormState = {
  birthFirstNames: "",
  birthMiddleNames: "",
  birthLastName: "",
  birthDate: "",
  birthTimeValue: "",
  birthTimePrecision: "unknown",
  birthPlaceDisplayName: "",
  birthPlaceCountryCode: "",
  currentFirstNames: "",
  currentMiddleNames: "",
  currentLastName: "",
  preferredName: "",
};

function buildPersonInput(form: FormState): PersonInput {
  const birthTime =
    form.birthTimeValue.trim() || form.birthTimePrecision !== "unknown"
      ? { value: form.birthTimeValue.trim() ? `${form.birthTimeValue}:00` : null, precision: form.birthTimePrecision }
      : null;

  const birthPlace = form.birthPlaceDisplayName.trim()
    ? {
        display_name: form.birthPlaceDisplayName.trim(),
        country_code: form.birthPlaceCountryCode.trim() || null,
      }
    : null;

  return {
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
  };
}

type Stage = "idle" | "creating-person" | "calculating" | "error";

function NewPersonForm() {
  const router = useRouter();
  const [form, setForm] = useState<FormState>(INITIAL_STATE);
  const [stage, setStage] = useState<Stage>("idle");
  const [error, setError] = useState<{ code: string; message: string } | null>(null);

  function update<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setStage("creating-person");
    try {
      const person = await api.people.create(buildPersonInput(form));
      setStage("calculating");
      const asOfDate = todayIsoDate();
      const calculation = await api.calculations.create(person.id, { as_of_date: asOfDate });
      recordCalculation({
        calculationId: calculation.id,
        personId: person.id,
        personLabel: form.preferredName.trim() || `${person.birth_first_names} ${person.birth_last_name}`,
        asOfDate,
      });
      router.push(`/analysis/${calculation.id}`);
    } catch (err) {
      setStage("error");
      if (err instanceof ApiError) {
        setError({ code: err.code, message: err.message });
      } else {
        setError({ code: "NETWORK_ERROR", message: "Could not reach the server." });
      }
    }
  }

  const submitting = stage === "creating-person" || stage === "calculating";

  return (
    <Card>
      <CardHeader>
        <CardTitle>New profile</CardTitle>
        <CardDescription>
          The birth name and birth date drive every Core Number. Everything else is optional.
        </CardDescription>
      </CardHeader>
      <CardContent>
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
              Birth time &amp; place <span className="font-sans text-xs font-normal text-muted">(metadata only — never affects a Core Number)</span>
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
                  onChange={(e) => update("birthTimePrecision", e.target.value as BirthTimePrecision)}
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
              Current name &amp; preferred name <span className="font-sans text-xs font-normal text-muted">(optional)</span>
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

          <Button type="submit" loading={submitting}>
            {stage === "creating-person" && "Creating profile…"}
            {stage === "calculating" && "Running calculation…"}
            {(stage === "idle" || stage === "error") && "Create profile & calculate"}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}

export default function NewPersonPage() {
  return (
    <AppShell>
      <div className="mb-8">
        <h1 className="font-serif text-3xl text-ivory">New profile</h1>
      </div>
      <NewPersonForm />
    </AppShell>
  );
}
