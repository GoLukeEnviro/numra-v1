"use client";

import { BrandMark } from "@/components/brand/logo";
import type { MessageKey } from "@/i18n/catalog";
import { useLocale } from "@/i18n/context";
import { useAuth } from "@/lib/auth-context";
import { cn } from "@/lib/utils";
import { ArrowLeft, LayoutGrid, ScrollText, Users } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

const ADMIN_NAV = [
  { href: "/admin", labelKey: "admin.nav.overview", icon: LayoutGrid, exact: true },
  { href: "/admin/users", labelKey: "admin.nav.users", icon: Users, exact: false },
  { href: "/admin/audit", labelKey: "admin.nav.audit", icon: ScrollText, exact: false },
] as const satisfies readonly {
  href: string;
  labelKey: MessageKey;
  icon: typeof Users;
  exact: boolean;
}[];

function isActive(pathname: string | null, href: string, exact: boolean): boolean {
  if (exact) return pathname === href;
  return pathname === href || (pathname?.startsWith(`${href}/`) ?? false);
}

/**
 * Deliberately separate from `AppShell`: the console needs its own, much smaller
 * navigation and must not inherit the product's mobile bottom bar (which would
 * cover admin actions). `AppShell` itself stays untouched.
 */
export function AdminShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { user } = useAuth();
  const { t } = useLocale();

  return (
    <div className="min-h-screen bg-background">
      <a
        href="#admin-content"
        className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-50 focus:rounded-lg focus:bg-gold focus:px-4 focus:py-2 focus:text-background"
      >
        {t("admin.nav.console")}
      </a>

      <header className="border-b border-white/10 bg-surface">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-4 gap-y-2 px-4 py-3 sm:px-6">
          <span className="flex items-center gap-2.5">
            <BrandMark className="h-8 w-8 shrink-0" />
            <span className="font-serif text-base leading-none text-ivory">
              {t("admin.nav.console")}
            </span>
          </span>
          <span className="ml-auto flex items-center gap-3">
            {user && (
              <span className="hidden max-w-[16rem] truncate text-xs text-muted sm:inline" title={user.email}>
                {user.email}
              </span>
            )}
            <Link
              href="/dashboard"
              className="inline-flex items-center gap-1.5 rounded-lg px-2 py-1.5 text-xs text-text transition-colors hover:bg-white/5 hover:text-ivory"
            >
              <ArrowLeft className="h-3.5 w-3.5" aria-hidden="true" />
              {t("admin.nav.backToApp")}
            </Link>
          </span>
        </div>

        {/* Its own scroll container, so a narrow phone never scrolls the body. */}
        <div className="mx-auto max-w-6xl overflow-x-auto px-4 sm:px-6">
          <nav aria-label={t("admin.nav.console")} className="flex min-w-max gap-1 pb-2">
            {ADMIN_NAV.map(({ href, labelKey, icon: Icon, exact }) => {
              const active = isActive(pathname, href, exact);
              return (
                <Link
                  key={href}
                  href={href}
                  aria-current={active ? "page" : undefined}
                  className={cn(
                    "flex items-center gap-2 rounded-lg px-3 py-2 text-sm transition-colors",
                    active ? "bg-gold/10 text-gold" : "text-text hover:bg-white/5 hover:text-ivory",
                  )}
                >
                  <Icon className="h-4 w-4" aria-hidden="true" />
                  {t(labelKey)}
                </Link>
              );
            })}
          </nav>
        </div>
      </header>

      <main id="admin-content" className="p-4 sm:p-6 lg:p-10">
        <div className="mx-auto max-w-6xl">{children}</div>
      </main>
    </div>
  );
}
