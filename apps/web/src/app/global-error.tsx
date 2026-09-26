"use client";

import { buttonVariants } from "@/components/ui/button";
import "./globals.css";

/**
 * Last-resort boundary for errors in the root layout itself. It replaces the whole
 * document, so the locale and auth providers are gone: the copy is German (the
 * default UI language) and the markup avoids every component that needs a provider.
 */
export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <html lang="de" data-theme="dark">
      <body className="bg-background">
        <main className="mx-auto flex min-h-screen max-w-xl flex-col justify-center px-4 text-center sm:px-6">
          <p className="font-serif text-xl text-ivory">AVENYTH</p>
          <h1 className="mt-6 font-serif text-3xl text-ivory">Diese Ansicht konnte nicht geladen werden.</h1>
          <p className="mt-4 text-sm text-muted">
            Beim Anzeigen ist ein unerwarteter Fehler aufgetreten. Versuche es erneut oder kehre zur
            Startseite zurück.
          </p>
          <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
            <button
              type="button"
              onClick={reset}
              className={buttonVariants({ size: "lg" })}
            >
              Erneut versuchen
            </button>
            {/* A plain anchor on purpose: a full reload rebuilds the broken root layout. */}
            {/* eslint-disable-next-line @next/next/no-html-link-for-pages */}
            <a href="/" className={buttonVariants({ variant: "secondary", size: "lg" })}>
              Zur Startseite
            </a>
          </div>
          {error.digest && (
            <p className="mt-6 font-mono text-xs text-muted">Fehlerreferenz: {error.digest}</p>
          )}
        </main>
      </body>
    </html>
  );
}
