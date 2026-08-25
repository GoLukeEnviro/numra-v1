"use client";

import { useState, type FormEvent, type ReactNode } from "react";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Button } from "@/components/ui/button";
import type { BirthTimePrecision, PersonInput } from "@/api/client";
import { useLocale } from "@/i18n/context";
import { todayIsoDate } from "@/lib/utils";

export interface PersonFormState {
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

const INITIAL_STATE: PersonFormState = {
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

export function buildPersonInput(form: PersonFormState): PersonInput {
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

/**
 * V1.6 B: the one person-creation form, shared by /people/new and /onboarding.
 * Owns only field state and layout; what happens on submit (create + calculate,
 * or create only) stays with the caller, which also owns submitting/error state.
 */
export function PersonForm({
  onSubmit,
  submitting,
  error,
  submitButton,
}: {
  onSubmit: (form: PersonFormState) => void;
  submitting: boolean;
  error: { code: string; message: string } | null;
  submitButton: ReactNode;
}) {
  const { t } = useLocale();
  const [form, setForm] = useState<PersonFormState>(INITIAL_STATE);

  function update<K extends keyof PersonFormState>(key: K, value: PersonFormState[K]) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    onSubmit(form);
  }

  return (
    <form onSubmit={handleSubmit} noValidate>
      <fieldset className="mb-6" disabled={submitting}>
        <legend className="mb-3 font-serif text-base text-ivory">{t("app.personForm.birthName")}</legend>
        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <Label htmlFor="birthFirstNames">{t("app.personForm.firstNames")}</Label>
            <Input
              id="birthFirstNames"
              required
              value={form.birthFirstNames}
              onChange={(e) => update("birthFirstNames", e.target.value)}
            />
          </div>
          <div>
            <Label htmlFor="birthLastName">{t("app.personForm.lastName")}</Label>
            <Input
              id="birthLastName"
              required
              value={form.birthLastName}
              onChange={(e) => update("birthLastName", e.target.value)}
            />
          </div>
          <div className="sm:col-span-2">
            <Label htmlFor="birthMiddleNames">{t("app.personForm.middleNames")}</Label>
            <Input
              id="birthMiddleNames"
              value={form.birthMiddleNames}
              onChange={(e) => update("birthMiddleNames", e.target.value)}
            />
          </div>
          <div>
            <Label htmlFor="birthDate">{t("app.personForm.birthDate")}</Label>
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
          {t("app.personForm.birthTimePlace")}{" "}
          <span className="font-sans text-xs font-normal text-muted">
            {t("app.personForm.birthTimePlaceNote")}
          </span>
        </legend>
        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <Label htmlFor="birthTimeValue">{t("app.personForm.birthTime")}</Label>
            <Input
              id="birthTimeValue"
              type="time"
              value={form.birthTimeValue}
              onChange={(e) => update("birthTimeValue", e.target.value)}
            />
          </div>
          <div>
            <Label htmlFor="birthTimePrecision">{t("app.personForm.timePrecision")}</Label>
            <Select
              id="birthTimePrecision"
              value={form.birthTimePrecision}
              onChange={(e) => update("birthTimePrecision", e.target.value as BirthTimePrecision)}
            >
              <option value="exact">{t("app.personForm.precisionExact")}</option>
              <option value="approximate">{t("app.personForm.precisionApproximate")}</option>
              <option value="unknown">{t("app.personForm.precisionUnknown")}</option>
            </Select>
          </div>
          <div>
            <Label htmlFor="birthPlaceDisplayName">{t("app.personForm.birthPlace")}</Label>
            <Input
              id="birthPlaceDisplayName"
              placeholder={t("app.personForm.birthPlacePlaceholder")}
              value={form.birthPlaceDisplayName}
              onChange={(e) => update("birthPlaceDisplayName", e.target.value)}
            />
          </div>
          <div>
            <Label htmlFor="birthPlaceCountryCode">{t("app.personForm.countryCode")}</Label>
            <Input
              id="birthPlaceCountryCode"
              placeholder={t("app.personForm.countryCodePlaceholder")}
              maxLength={2}
              value={form.birthPlaceCountryCode}
              onChange={(e) => update("birthPlaceCountryCode", e.target.value.toUpperCase())}
            />
          </div>
        </div>
      </fieldset>

      <fieldset className="mb-6" disabled={submitting}>
        <legend className="mb-3 font-serif text-base text-ivory">
          {t("app.personForm.currentPreferred")}{" "}
          <span className="font-sans text-xs font-normal text-muted">{t("app.personForm.optionalNote")}</span>
        </legend>
        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <Label htmlFor="currentFirstNames">{t("app.personForm.currentFirstNames")}</Label>
            <Input
              id="currentFirstNames"
              value={form.currentFirstNames}
              onChange={(e) => update("currentFirstNames", e.target.value)}
            />
          </div>
          <div>
            <Label htmlFor="currentLastName">{t("app.personForm.currentLastName")}</Label>
            <Input
              id="currentLastName"
              value={form.currentLastName}
              onChange={(e) => update("currentLastName", e.target.value)}
            />
          </div>
          <div>
            <Label htmlFor="currentMiddleNames">{t("app.personForm.currentMiddleNames")}</Label>
            <Input
              id="currentMiddleNames"
              value={form.currentMiddleNames}
              onChange={(e) => update("currentMiddleNames", e.target.value)}
            />
          </div>
          <div>
            <Label htmlFor="preferredName">{t("app.personForm.preferredName")}</Label>
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
        {submitButton}
      </Button>
    </form>
  );
}
