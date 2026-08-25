"use client";

import { Logo } from "@/components/brand/logo";
import { NumericWheel } from "@/components/layout/numeric-wheel";
import { LinkButton } from "@/components/ui/link-button";
import { useLocale } from "@/i18n/context";
import type { MessageKey } from "@/i18n/catalog";
import { useAuth } from "@/lib/auth-context";
import {
  BookOpen,
  Calculator,
  GitCompareArrows,
  History,
  LayoutGrid,
  ScrollText,
  Sunrise,
  UserRound,
  Users,
  type LucideIcon,
} from "lucide-react";
import Link from "next/link";

const HOW_STEPS: { titleKey: MessageKey; bodyKey: MessageKey }[] = [
  { titleKey: "public.landing.howStep1Title", bodyKey: "public.landing.howStep1Body" },
  { titleKey: "public.landing.howStep2Title", bodyKey: "public.landing.howStep2Body" },
  { titleKey: "public.landing.howStep3Title", bodyKey: "public.landing.howStep3Body" },
];

const FEATURES: { icon: LucideIcon; titleKey: MessageKey; bodyKey: MessageKey }[] = [
  { icon: UserRound, titleKey: "public.landing.featureProfileTitle", bodyKey: "public.landing.featureProfileBody" },
  { icon: Calculator, titleKey: "public.landing.featureCoreTitle", bodyKey: "public.landing.featureCoreBody" },
  { icon: Sunrise, titleKey: "public.landing.featureTodayTitle", bodyKey: "public.landing.featureTodayBody" },
  { icon: GitCompareArrows, titleKey: "public.landing.featureRelationshipsTitle", bodyKey: "public.landing.featureRelationshipsBody" },
  { icon: BookOpen, titleKey: "public.landing.featureReportsTitle", bodyKey: "public.landing.featureReportsBody" },
  { icon: History, titleKey: "public.landing.featureHistoryTitle", bodyKey: "public.landing.featureHistoryBody" },
];

function SectionHeading({ children }: { children: React.ReactNode }) {
  return <h2 className="font-serif text-2xl text-ivory sm:text-3xl">{children}</h2>;
}

/**
 * V1.6 B: the public landing page. Anonymous visitors are no longer redirected to
 * /login — this page is Numra's front door. A signed-in visitor keeps the page and
 * additionally gets a prominent way back into the product (never an auto-redirect).
 */
export default function LandingPage() {
  const { status } = useAuth();
  const { t } = useLocale();
  const authenticated = status === "authenticated";

  return (
    <div className="min-h-screen bg-background">
      <header className="border-b border-white/10">
        <nav
          aria-label={t("nav.primary")}
          className="mx-auto flex max-w-6xl items-center justify-between gap-3 px-4 py-4 sm:px-6"
        >
          <Link href="/" className="inline-flex items-center">
            <Logo markClassName="h-9 w-9" textClassName="text-xl" />
          </Link>
          <div className="flex items-center gap-2">
            {authenticated ? (
              <LinkButton href="/dashboard" size="sm">
                {t("public.landing.toDashboard")}
              </LinkButton>
            ) : (
              <>
                <LinkButton href="/login" variant="ghost" size="sm">
                  {t("public.landing.navSignIn")}
                </LinkButton>
                <LinkButton href="/register" size="sm">
                  {t("public.landing.navCreateAccount")}
                </LinkButton>
              </>
            )}
          </div>
        </nav>
      </header>

      <main>
        {/* HERO */}
        <section className="sacred-wheel-bg relative overflow-hidden border-b border-white/10">
          <NumericWheel className="pointer-events-none absolute -right-28 -top-28 h-96 w-96 opacity-30" />
          <div className="relative mx-auto max-w-6xl px-4 py-20 sm:px-6 sm:py-28">
            <div className="max-w-2xl animate-rise-in">
              <p className="mb-4 text-xs uppercase tracking-[0.2em] text-bronze">
                {t("public.landing.heroEyebrow")}
              </p>
              <h1 className="font-serif text-4xl leading-tight text-ivory sm:text-5xl">
                {t("public.landing.heroTitle")}
              </h1>
              <p className="mt-5 max-w-reading text-base leading-relaxed text-muted">
                {t("public.landing.heroSubtitle")}
              </p>
              <div className="mt-8 flex flex-wrap items-center gap-3">
                {authenticated ? (
                  <>
                    <p className="w-full text-sm text-muted">{t("public.landing.signedInHint")}</p>
                    <LinkButton href="/dashboard" size="lg">
                      {t("public.landing.toDashboard")}
                    </LinkButton>
                  </>
                ) : (
                  <>
                    <LinkButton href="/register" size="lg">
                      {t("public.landing.heroCtaCreate")}
                    </LinkButton>
                    <LinkButton href="/login" variant="secondary" size="lg">
                      {t("public.landing.heroCtaSignIn")}
                    </LinkButton>
                  </>
                )}
              </div>
            </div>
          </div>
        </section>

        {/* HOW IT WORKS */}
        <section className="mx-auto max-w-6xl px-4 py-16 sm:px-6">
          <SectionHeading>{t("public.landing.howTitle")}</SectionHeading>
          <ol className="mt-8 grid gap-4 sm:grid-cols-3">
            {HOW_STEPS.map(({ titleKey, bodyKey }, index) => (
              <li
                key={titleKey}
                className="rounded-xl border border-white/10 bg-surface p-6"
              >
                <p aria-hidden="true" className="font-mono text-sm text-bronze">
                  {String(index + 1).padStart(2, "0")}
                </p>
                <h3 className="mt-3 font-serif text-lg text-ivory">{t(titleKey)}</h3>
                <p className="mt-2 text-sm leading-relaxed text-muted">{t(bodyKey)}</p>
              </li>
            ))}
          </ol>
        </section>

        {/* FEATURES */}
        <section className="border-t border-white/10 bg-surface/40">
          <div className="mx-auto max-w-6xl px-4 py-16 sm:px-6">
            <SectionHeading>{t("public.landing.featuresTitle")}</SectionHeading>
            <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {FEATURES.map(({ icon: Icon, titleKey, bodyKey }) => (
                <div key={titleKey} className="rounded-xl border border-white/10 bg-surface p-5">
                  <span className="flex items-center gap-2.5">
                    <Icon className="h-4 w-4 text-gold" aria-hidden="true" />
                    <h3 className="font-serif text-base text-ivory">{t(titleKey)}</h3>
                  </span>
                  <p className="mt-2 text-sm leading-relaxed text-muted">{t(bodyKey)}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* TRANSPARENCY & PRIVACY */}
        <section className="mx-auto grid max-w-6xl gap-4 px-4 py-16 sm:px-6 lg:grid-cols-2">
          <div className="rounded-xl border border-white/10 bg-surface p-6 sm:p-8">
            <span className="flex items-center gap-2.5">
              <LayoutGrid className="h-4 w-4 text-gold" aria-hidden="true" />
              <h2 className="font-serif text-xl text-ivory">{t("public.landing.transparencyTitle")}</h2>
            </span>
            <p className="mt-3 text-sm leading-relaxed text-muted">
              {t("public.landing.transparencyBody")}
            </p>
          </div>
          <div className="rounded-xl border border-white/10 bg-surface p-6 sm:p-8">
            <span className="flex items-center gap-2.5">
              <Users className="h-4 w-4 text-gold" aria-hidden="true" />
              <h2 className="font-serif text-xl text-ivory">{t("public.landing.privacyTitle")}</h2>
            </span>
            <p className="mt-3 text-sm leading-relaxed text-muted">
              {t("public.landing.privacyBody")}
            </p>
          </div>
        </section>

        {/* DISCLAIMER */}
        <section className="mx-auto max-w-6xl px-4 pb-16 sm:px-6">
          <div
            role="note"
            className="rounded-xl border border-white/10 bg-surface-2 p-6 sm:p-8"
          >
            <span className="flex items-center gap-2.5">
              <ScrollText className="h-4 w-4 text-muted" aria-hidden="true" />
              <h2 className="font-serif text-lg text-ivory">{t("public.landing.disclaimerTitle")}</h2>
            </span>
            <p className="mt-3 text-sm leading-relaxed text-muted">
              {t("public.landing.disclaimerBody")}
            </p>
          </div>
        </section>

        {/* FINAL CTA */}
        <section className="border-t border-white/10">
          <div className="mx-auto max-w-6xl px-4 py-16 text-center sm:px-6">
            <h2 className="font-serif text-2xl text-ivory sm:text-3xl">
              {t("public.landing.finalCtaTitle")}
            </h2>
            <p className="mt-3 text-sm text-muted">{t("public.landing.finalCtaBody")}</p>
            <div className="mt-6 flex flex-wrap items-center justify-center gap-3">
              {authenticated ? (
                <LinkButton href="/dashboard" size="lg">
                  {t("public.landing.toDashboard")}
                </LinkButton>
              ) : (
                <>
                  <LinkButton href="/register" size="lg">
                    {t("public.landing.heroCtaCreate")}
                  </LinkButton>
                  <LinkButton href="/login" variant="secondary" size="lg">
                    {t("public.landing.heroCtaSignIn")}
                  </LinkButton>
                </>
              )}
            </div>
          </div>
        </section>
      </main>

      <footer className="border-t border-white/10">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-4 px-4 py-8 sm:px-6">
          <Logo markClassName="h-7 w-7" textClassName="text-base" />
          <nav aria-label={t("public.landing.footerPrivacy")} className="flex flex-wrap gap-5 text-sm text-muted">
            <Link href="/login" className="transition-colors hover:text-gold">
              {t("public.landing.navSignIn")}
            </Link>
            <Link href="/register" className="transition-colors hover:text-gold">
              {t("public.landing.navCreateAccount")}
            </Link>
            <Link href="/settings/privacy" className="transition-colors hover:text-gold">
              {t("public.landing.footerPrivacy")}
            </Link>
          </nav>
        </div>
      </footer>
    </div>
  );
}
