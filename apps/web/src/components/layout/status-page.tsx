import { Logo } from "@/components/brand/logo";
import Link from "next/link";

/**
 * Shared frame for the 404 page and the error boundaries: the brand header and a
 * centred message block, so a dead end still looks and reads like AVENYTH rather
 * than Next's white English default.
 */
export function StatusPage({
  eyebrow,
  title,
  body,
  children,
}: {
  eyebrow?: string;
  title: string;
  body: string;
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
      <main className="mx-auto flex w-full max-w-xl flex-1 flex-col justify-center px-4 py-16 text-center sm:px-6">
        {eyebrow && <p className="font-mono text-xs uppercase tracking-widest text-gold">{eyebrow}</p>}
        <h1 className="mt-3 font-serif text-3xl text-ivory sm:text-4xl">{title}</h1>
        <p className="mt-4 text-sm text-muted">{body}</p>
        <div className="mt-8 flex flex-wrap items-center justify-center gap-3">{children}</div>
      </main>
    </div>
  );
}
