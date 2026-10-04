import { Logo } from "@/components/brand/logo";
import { PublicFooter } from "@/components/layout/public-footer";
import Link from "next/link";

/**
 * Frame for /impressum and /datenschutz. Server-rendered on purpose: the legal text
 * is in the first HTML response, readable without JavaScript and without a session.
 * Only the footer is a client component (it needs the locale for its link labels).
 */
export function LegalDocument({
  title,
  lastUpdated,
  children,
}: {
  title: string;
  lastUpdated?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex min-h-screen flex-col bg-background">
      <header className="border-b border-white/10">
        <div className="mx-auto flex max-w-6xl items-center px-4 py-4 sm:px-6">
          <Link href="/" className="inline-flex items-center">
            <Logo markClassName="h-9 w-9" textClassName="text-xl" />
          </Link>
        </div>
      </header>
      <main className="mx-auto w-full max-w-3xl flex-1 px-4 py-12 sm:px-6 sm:py-16">
        <h1 className="font-serif text-3xl text-ivory sm:text-4xl">{title}</h1>
        {lastUpdated && <p className="mt-2 text-sm text-muted">Stand: {lastUpdated}</p>}
        <div className="mt-8 space-y-10 text-sm leading-relaxed text-text">{children}</div>
      </main>
      <PublicFooter />
    </div>
  );
}

export function LegalSection({ id, title, children }: { id?: string; title: string; children: React.ReactNode }) {
  return (
    <section id={id} aria-labelledby={id ? `${id}-title` : undefined} className="space-y-3">
      <h2 id={id ? `${id}-title` : undefined} className="font-serif text-xl text-ivory">
        {title}
      </h2>
      {children}
    </section>
  );
}

export function LegalList({ children }: { children: React.ReactNode }) {
  return <ul className="list-disc space-y-1.5 pl-5">{children}</ul>;
}
