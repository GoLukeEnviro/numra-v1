"use client";

import { BrandMark } from "@/components/brand/logo";
import { RequireAuth } from "@/components/layout/require-auth";
import { Button } from "@/components/ui/button";
import type { MessageKey } from "@/i18n/catalog";
import { useLocale } from "@/i18n/context";
import { useAuth } from "@/lib/auth-context";
import { cn } from "@/lib/utils";
import {
    BookOpen,
    GitCompareArrows,
    LayoutGrid,
    LogOut,
    MoreHorizontal,
    Plus,
    Settings,
    Sunrise,
    Users,
    X,
} from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useState } from "react";

// Today leads: it is the lightest, most-returned-to view, and the only one that
// answers a question about *now* rather than about a stored record.
const NAV = [
  { href: "/today", labelKey: "nav.today", icon: Sunrise },
  { href: "/dashboard", labelKey: "nav.dashboard", icon: LayoutGrid },
  { href: "/people", labelKey: "nav.people", icon: Users },
  { href: "/reports", labelKey: "nav.reports", icon: BookOpen },
  { href: "/relationships", labelKey: "nav.relationships", icon: GitCompareArrows },
  { href: "/settings", labelKey: "nav.settings", icon: Settings },
] as const satisfies readonly { href: string; labelKey: MessageKey; icon: typeof Sunrise }[];

// Mobile-first V1.5 Epic H: the desktop sidebar's full item set doesn't fit a fixed
// bottom bar. These four are the ones a phone visit is most likely to be *for* — the
// rest (Dashboard, Reports, Settings) plus Logout live behind "More", which mobile
// still needs a real way to reach Logout from (previously desktop-only).
const MOBILE_PRIMARY = [
  { href: "/today", labelKey: "nav.today", icon: Sunrise },
  { href: "/people", labelKey: "nav.people", icon: Users },
  { href: "/relationships", labelKey: "nav.relationships", icon: GitCompareArrows },
] as const satisfies readonly { href: string; labelKey: MessageKey; icon: typeof Sunrise }[];

const MOBILE_MORE = [
  { href: "/dashboard", labelKey: "nav.dashboard", icon: LayoutGrid },
  { href: "/reports", labelKey: "nav.reports", icon: BookOpen },
  { href: "/settings", labelKey: "nav.settings", icon: Settings },
] as const satisfies readonly { href: string; labelKey: MessageKey; icon: typeof Sunrise }[];

function isActive(pathname: string | null, href: string): boolean {
  return pathname === href || (pathname?.startsWith(`${href}/`) ?? false);
}

function MobileMoreSheet({
  open,
  onClose,
  onLogout,
  userEmail,
}: {
  open: boolean;
  onClose: () => void;
  onLogout: () => void;
  userEmail: string | undefined;
}) {
  const pathname = usePathname();
  const { t } = useLocale();
  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 md:hidden"
      role="dialog"
      aria-modal="true"
      aria-label={t("nav.more")}
    >
      <button
        type="button"
        aria-label="Dismiss"
        onClick={onClose}
        className="absolute inset-0 bg-black/60"
      />
      <div
        className="absolute inset-x-0 bottom-0 rounded-t-2xl border-t border-white/10 bg-surface p-4"
        style={{ paddingBottom: "calc(env(safe-area-inset-bottom, 0px) + 1rem)" }}
      >
        <div className="mb-3 flex items-center justify-between">
          <p className="font-serif text-lg text-ivory">{t("nav.more")}</p>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close menu"
            className="rounded-lg p-2 text-muted hover:bg-white/5 hover:text-ivory"
          >
            <X className="h-5 w-5" aria-hidden="true" />
          </button>
        </div>
        <nav className="flex flex-col gap-1">
          {MOBILE_MORE.map(({ href, labelKey, icon: Icon }) => {
            const active = isActive(pathname, href);
            return (
              <Link
                key={href}
                href={href}
                onClick={onClose}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "flex items-center gap-3 rounded-lg px-3 py-3 text-sm transition-colors",
                  active ? "bg-gold/10 text-gold" : "text-text hover:bg-white/5 hover:text-ivory",
                )}
              >
                <Icon className="h-5 w-5" aria-hidden="true" />
                {t(labelKey)}
              </Link>
            );
          })}
        </nav>
        <div className="mt-3 border-t border-white/10 pt-3">
          {userEmail && <p className="mb-2 truncate px-3 text-xs text-muted">{userEmail}</p>}
          <button
            type="button"
            onClick={onLogout}
            className="flex w-full items-center gap-3 rounded-lg px-3 py-3 text-sm text-text transition-colors hover:bg-white/5 hover:text-ivory"
          >
            <LogOut className="h-5 w-5" aria-hidden="true" />
            {t("nav.logout")}
          </button>
        </div>
      </div>
    </div>
  );
}

function MobileBottomNav({
  onLogout,
  userEmail,
}: {
  onLogout: () => void;
  userEmail: string | undefined;
}) {
  const pathname = usePathname();
  const { t } = useLocale();
  const [moreOpen, setMoreOpen] = useState(false);
  const moreActive = MOBILE_MORE.some((item) => isActive(pathname, item.href));

  return (
    <>
      <nav
        aria-label={t("nav.primary")}
        className="fixed inset-x-0 bottom-0 z-40 border-t border-white/10 bg-surface md:hidden"
        style={{ paddingBottom: "env(safe-area-inset-bottom, 0px)" }}
      >
        <div className="grid grid-cols-5">
          {MOBILE_PRIMARY.slice(0, 2).map(({ href, labelKey, icon: Icon }) => {
            const active = isActive(pathname, href);
            return (
              <Link
                key={href}
                href={href}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "flex flex-col items-center gap-1 py-2.5 text-[11px]",
                  active ? "text-gold" : "text-muted",
                )}
              >
                <Icon className="h-5 w-5" aria-hidden="true" />
                {t(labelKey)}
              </Link>
            );
          })}

          <Link
            href="/people/new"
            aria-label={t("nav.newProfile")}
            className="flex flex-col items-center justify-center gap-1 py-2 text-[11px] text-muted"
          >
            <span className="flex h-9 w-9 items-center justify-center rounded-full bg-gold text-background shadow-gold">
              <Plus className="h-5 w-5" aria-hidden="true" />
            </span>
          </Link>

          {MOBILE_PRIMARY.slice(2).map(({ href, labelKey, icon: Icon }) => {
            const active = isActive(pathname, href);
            return (
              <Link
                key={href}
                href={href}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "flex flex-col items-center gap-1 py-2.5 text-[11px]",
                  active ? "text-gold" : "text-muted",
                )}
              >
                <Icon className="h-5 w-5" aria-hidden="true" />
                {t(labelKey)}
              </Link>
            );
          })}

          <button
            type="button"
            onClick={() => setMoreOpen(true)}
            aria-haspopup="dialog"
            aria-expanded={moreOpen}
            className={cn(
              "flex flex-col items-center gap-1 py-2.5 text-[11px]",
              moreActive ? "text-gold" : "text-muted",
            )}
          >
            <MoreHorizontal className="h-5 w-5" aria-hidden="true" />
            {t("nav.more")}
          </button>
        </div>
      </nav>

      <MobileMoreSheet
        open={moreOpen}
        onClose={() => setMoreOpen(false)}
        onLogout={() => {
          setMoreOpen(false);
          onLogout();
        }}
        userEmail={userEmail}
      />
    </>
  );
}

function AppShellInner({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { user, logout } = useAuth();
  const { t } = useLocale();

  async function handleLogout() {
    await logout();
    router.push("/login");
  }

  return (
    <div className="min-h-screen bg-background">
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-50 focus:rounded-lg focus:bg-gold focus:px-4 focus:py-2 focus:text-background"
      >
        Skip to content
      </a>
      <div className="flex min-h-screen flex-col md:flex-row">
        <aside className="border-b border-white/10 bg-surface md:w-64 md:shrink-0 md:border-b-0 md:border-r">
          <div className="flex items-center gap-3 p-5">
            <BrandMark className="h-9 w-9 shrink-0" />
            <div>
              <p className="flex items-center gap-1.5 font-serif text-lg leading-none text-ivory">
                Numra
                <span aria-hidden="true" className="h-1 w-1 rounded-full bg-gold" />
              </p>
              <p className="text-xs text-muted">Numerology, made auditable</p>
            </div>
          </div>
          {/* Desktop-only: mobile uses the fixed bottom nav instead (below). */}
          <nav className="hidden gap-1 px-3 pb-3 md:flex md:flex-col md:pb-0">
            {NAV.map(({ href, labelKey, icon: Icon }) => {
              const active = isActive(pathname, href);
              return (
                <Link
                  key={href}
                  href={href}
                  className={cn(
                    "flex shrink-0 items-center gap-2.5 rounded-lg px-3 py-2 text-sm transition-colors",
                    active
                      ? "bg-gold/10 text-gold"
                      : "text-text hover:bg-white/5 hover:text-ivory",
                  )}
                  aria-current={active ? "page" : undefined}
                >
                  <Icon className="h-4 w-4" aria-hidden="true" />
                  {t(labelKey)}
                </Link>
              );
            })}
          </nav>
          <div className="hidden border-t border-white/10 p-4 md:block">
            {user && (
              <p className="mb-3 truncate text-xs text-muted" title={user.email}>
                {user.email}
              </p>
            )}
            <Button variant="ghost" size="sm" className="w-full justify-start" onClick={handleLogout}>
              <LogOut className="h-4 w-4" aria-hidden="true" />
              {t("nav.logout")}
            </Button>
          </div>
        </aside>
        <main
          id="main-content"
          className="flex-1 p-4 pb-[max(6rem,calc(env(safe-area-inset-bottom,0px)+5rem))] sm:p-6 md:pb-6 lg:p-10"
        >
          <div className="mx-auto max-w-6xl">{children}</div>
        </main>
      </div>
      <MobileBottomNav onLogout={handleLogout} userEmail={user?.email} />
    </div>
  );
}

export function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <RequireAuth>
      <AppShellInner>{children}</AppShellInner>
    </RequireAuth>
  );
}
