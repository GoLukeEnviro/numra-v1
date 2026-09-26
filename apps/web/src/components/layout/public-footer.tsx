"use client";

import { Logo } from "@/components/brand/logo";
import { useLocale } from "@/i18n/context";
import { cn } from "@/lib/utils";
import Link from "next/link";

const LINK_CLASS = "transition-colors hover:text-gold";

/**
 * Impressum + Datenschutz as a compact link row. Reachable without a session from
 * every public page and from inside the app — § 5 DDG requires the Impressum to be
 * "unmittelbar erreichbar", and Art. 13 DSGVO needs the privacy notice before any
 * data is collected (i.e. before /register).
 */
export function LegalLinks({ className }: { className?: string }) {
  const { t } = useLocale();
  return (
    <nav aria-label={t("public.legal.navLabel")} className={cn("flex flex-wrap gap-5 text-sm text-muted", className)}>
      <Link href="/impressum" className={LINK_CLASS}>
        {t("public.legal.imprint")}
      </Link>
      <Link href="/datenschutz" className={LINK_CLASS}>
        {t("public.legal.privacy")}
      </Link>
    </nav>
  );
}

/** Full footer for the landing page and the legal pages. */
export function PublicFooter() {
  const { t } = useLocale();
  return (
    <footer className="border-t border-white/10">
      <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-4 px-4 py-8 sm:px-6">
        <Link href="/" className="inline-flex items-center">
          <Logo markClassName="h-7 w-7" textClassName="text-base" />
        </Link>
        <div className="flex flex-wrap items-center gap-5 text-sm text-muted">
          <Link href="/login" className={LINK_CLASS}>
            {t("public.landing.navSignIn")}
          </Link>
          <Link href="/register" className={LINK_CLASS}>
            {t("public.landing.navCreateAccount")}
          </Link>
          <LegalLinks />
        </div>
      </div>
    </footer>
  );
}
