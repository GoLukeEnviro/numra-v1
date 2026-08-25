"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { AppShell } from "@/components/layout/app-shell";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { buildPersonInput, PersonForm, type PersonFormState } from "@/components/people/person-form";
import { api, ApiError } from "@/api/client";
import { useLocale } from "@/i18n/context";
import { recordCalculation } from "@/lib/local-calculations";
import { todayIsoDate } from "@/lib/utils";

type Stage = "idle" | "creating-person" | "calculating" | "error";

function NewPersonForm() {
  const router = useRouter();
  const { t } = useLocale();
  const [stage, setStage] = useState<Stage>("idle");
  const [error, setError] = useState<{ code: string; message: string } | null>(null);

  async function handleSubmit(form: PersonFormState) {
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
        setError({ code: "NETWORK_ERROR", message: t("common.networkError") });
      }
    }
  }

  const submitting = stage === "creating-person" || stage === "calculating";

  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("app.peopleNew.title")}</CardTitle>
        <CardDescription>{t("app.peopleNew.description")}</CardDescription>
      </CardHeader>
      <CardContent>
        <PersonForm
          onSubmit={(form) => void handleSubmit(form)}
          submitting={submitting}
          error={error}
          submitButton={
            <>
              {stage === "creating-person" && t("app.peopleNew.creating")}
              {stage === "calculating" && t("app.peopleNew.calculating")}
              {(stage === "idle" || stage === "error") && t("app.peopleNew.submit")}
            </>
          }
        />
      </CardContent>
    </Card>
  );
}

export default function NewPersonPage() {
  const { t } = useLocale();
  return (
    <AppShell>
      <div className="mb-8">
        <h1 className="font-serif text-3xl text-ivory">{t("app.peopleNew.title")}</h1>
      </div>
      <NewPersonForm />
    </AppShell>
  );
}
