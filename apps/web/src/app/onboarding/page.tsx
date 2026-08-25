"use client";

import { api, ApiError, type PersonOut } from "@/api/client";
import { Logo } from "@/components/brand/logo";
import { RequireAuth } from "@/components/layout/require-auth";
import { NumericWheel } from "@/components/layout/numeric-wheel";
import { buildPersonInput, PersonForm, type PersonFormState } from "@/components/people/person-form";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { LinkButton } from "@/components/ui/link-button";
import { LoadingState, ErrorState } from "@/components/ui/states";
import { useLocale } from "@/i18n/context";
import { recordCalculation } from "@/lib/local-calculations";
import { personDisplayName } from "@/lib/identity";
import { useAsync } from "@/lib/use-async";
import { todayIsoDate } from "@/lib/utils";
import { ArrowRight, CheckCircle2, Sparkles } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";

type Step = "welcome" | "profile" | "calculation" | "done";

const STEP_ORDER: Step[] = ["welcome", "profile", "calculation", "done"];

function StepIndicator({ step }: { step: Step }) {
  const { t } = useLocale();
  const index = STEP_ORDER.indexOf(step);
  return (
    <p className="text-xs uppercase tracking-[0.2em] text-bronze">
      {t("public.onboarding.stepLabel")} {index + 1} {t("public.onboarding.of")} {STEP_ORDER.length}
    </p>
  );
}

/**
 * V1.6 B first-run flow. State lives entirely in this component — there is no
 * onboarding persistence anywhere. Profile and calculation reuse the exact same
 * APIs as /people/new; no numerology logic exists in the browser.
 */
function OnboardingContent() {
  const { t } = useLocale();
  const router = useRouter();
  const peopleState = useAsync(() => api.people.list(), []);
  const [step, setStep] = useState<Step>("welcome");
  const [person, setPerson] = useState<PersonOut | null>(null);
  const [personLabel, setPersonLabel] = useState("");
  const [calculationId, setCalculationId] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<{ code: string; message: string } | null>(null);

  function reportError(err: unknown) {
    setError(
      err instanceof ApiError
        ? { code: err.code, message: err.message }
        : { code: "NETWORK_ERROR", message: t("common.networkError") },
    );
  }

  async function handleCreateProfile(form: PersonFormState) {
    setSubmitting(true);
    setError(null);
    try {
      const created = await api.people.create(buildPersonInput(form));
      setPerson(created);
      setPersonLabel(personDisplayName(created));
      setStep("calculation");
    } catch (err) {
      reportError(err);
    } finally {
      setSubmitting(false);
    }
  }

  async function handleRunCalculation() {
    if (!person) return;
    setSubmitting(true);
    setError(null);
    try {
      const asOfDate = todayIsoDate();
      const calculation = await api.calculations.create(person.id, { as_of_date: asOfDate });
      recordCalculation({
        calculationId: calculation.id,
        personId: person.id,
        personLabel,
        asOfDate,
      });
      setCalculationId(calculation.id);
      setStep("done");
    } catch (err) {
      reportError(err);
    } finally {
      setSubmitting(false);
    }
  }

  if (peopleState.status === "loading") {
    return <LoadingState label={t("common.loading")} />;
  }
  if (peopleState.status === "error") {
    return <ErrorState error={peopleState.error} onRetry={peopleState.reload} />;
  }

  // An account that already has people never gets forced back through onboarding —
  // and never creates a duplicate first profile from here.
  if (peopleState.data.length > 0 && step === "welcome") {
    return (
      <Card className="animate-rise-in shadow-elevated">
        <CardContent className="p-8 text-center sm:p-10">
          <CheckCircle2 className="mx-auto h-8 w-8 text-gold" aria-hidden="true" />
          <h2 className="mt-4 font-serif text-2xl text-ivory">
            {t("public.onboarding.existingTitle")}
          </h2>
          <p className="mx-auto mt-2 max-w-md text-sm text-muted">
            {t("public.onboarding.existingBody")}
          </p>
          <LinkButton href="/dashboard" className="mt-6">
            {t("public.landing.toDashboard")}
            <ArrowRight className="h-4 w-4" aria-hidden="true" />
          </LinkButton>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="animate-rise-in">
      {step === "welcome" && (
        <Card className="shadow-elevated">
          <CardContent className="p-8 sm:p-10">
            <StepIndicator step={step} />
            <h2 className="mt-3 font-serif text-3xl text-ivory">
              {t("public.onboarding.welcomeTitle")}
            </h2>
            <p className="mt-3 max-w-reading text-sm leading-relaxed text-muted">
              {t("public.onboarding.welcomeBody")}
            </p>
            <Button className="mt-6" onClick={() => setStep("profile")}>
              {t("public.onboarding.start")}
              <ArrowRight className="h-4 w-4" aria-hidden="true" />
            </Button>
          </CardContent>
        </Card>
      )}

      {step === "profile" && (
        <Card className="shadow-elevated">
          <CardContent className="p-6 sm:p-8">
            <StepIndicator step={step} />
            <h2 className="mt-3 font-serif text-2xl text-ivory">
              {t("public.onboarding.profileTitle")}
            </h2>
            <p className="mb-6 mt-2 text-sm text-muted">{t("public.onboarding.profileBody")}</p>
            <PersonForm
              onSubmit={(form) => void handleCreateProfile(form)}
              submitting={submitting}
              error={error}
              submitButton={
                submitting ? t("public.onboarding.creating") : t("public.onboarding.start")
              }
            />
          </CardContent>
        </Card>
      )}

      {step === "calculation" && (
        <Card className="shadow-elevated">
          <CardContent className="p-8 sm:p-10">
            <StepIndicator step={step} />
            <h2 className="mt-3 font-serif text-2xl text-ivory">
              {t("public.onboarding.calcTitle")}
            </h2>
            <p className="mt-2 max-w-reading text-sm text-muted">
              {personLabel && <span className="text-ivory">{personLabel} — </span>}
              {t("public.onboarding.calcBody")}
            </p>
            {error && (
              <div
                role="alert"
                className="mt-4 rounded-lg border border-danger/30 bg-danger-surface p-3 text-sm text-text"
              >
                <span className="mr-1.5 rounded bg-black/20 px-1.5 py-0.5 font-mono text-xs">
                  {error.code}
                </span>
                {error.message}
              </div>
            )}
            <Button className="mt-6" onClick={() => void handleRunCalculation()} loading={submitting}>
              <Sparkles className="h-4 w-4" aria-hidden="true" />
              {submitting ? t("public.onboarding.calcRunning") : t("public.onboarding.runCalculation")}
            </Button>
          </CardContent>
        </Card>
      )}

      {step === "done" && (
        <Card className="shadow-elevated">
          <CardContent className="p-8 text-center sm:p-10">
            <StepIndicator step={step} />
            <CheckCircle2 className="mx-auto mt-4 h-8 w-8 text-gold" aria-hidden="true" />
            <h2 className="mt-4 font-serif text-2xl text-ivory">
              {t("public.onboarding.doneTitle")}
            </h2>
            <p className="mx-auto mt-2 max-w-md text-sm text-muted">
              {t("public.onboarding.doneBody")}
            </p>
            <div className="mt-6 flex flex-wrap items-center justify-center gap-3">
              <Button onClick={() => router.replace("/dashboard")}>
                {t("public.landing.toDashboard")}
              </Button>
              {calculationId && (
                <LinkButton variant="secondary" href={`/analysis/${calculationId}`}>
                  {t("public.onboarding.openAnalysis")}
                  <ArrowRight className="h-4 w-4" aria-hidden="true" />
                </LinkButton>
              )}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

export default function OnboardingPage() {
  return (
    <RequireAuth>
      <div className="sacred-wheel-bg relative min-h-screen overflow-hidden bg-background">
        <NumericWheel className="pointer-events-none absolute -right-24 -top-24 h-96 w-96 opacity-30" />
        <div className="relative mx-auto max-w-2xl px-4 py-10 sm:px-6 sm:py-16">
          <h1 className="mb-8">
            <Logo markClassName="h-10 w-10" textClassName="text-2xl" />
          </h1>
          <OnboardingContent />
        </div>
      </div>
    </RequireAuth>
  );
}
