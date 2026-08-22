"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { RequireAuth } from "@/components/layout/require-auth";
import { NumericWheel } from "@/components/layout/numeric-wheel";
import { Button } from "@/components/ui/button";
import {
  LogOut,
  Users,
  LayoutGrid,
  GitCompareArrows,
  Settings,
  Sunrise,
  BookOpen,
} from "lucide-react";
import { cn } from "@/lib/utils";

// Today leads: it is the lightest, most-returned-to view, and the only one that
// answers a question about *now* rather than about a stored record.
const NAV = [
  { href: "/today", label: "Today", icon: Sunrise },
  { href: "/dashboard", label: "Dashboard", icon: LayoutGrid },
  { href: "/people", label: "People", icon: Users },
  { href: "/reports", label: "Reports", icon: BookOpen },
  { href: "/relationships", label: "Relationships", icon: GitCompareArrows },
  { href: "/settings", label: "Settings", icon: Settings },
];

function AppShellInner({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { user, logout } = useAuth();

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
            <NumericWheel className="h-9 w-9 shrink-0" />
            <div>
              <p className="font-serif text-lg leading-none text-ivory">Numra</p>
              <p className="text-xs text-muted">Numerology, made auditable</p>
            </div>
          </div>
          <nav className="flex gap-1 overflow-x-auto px-3 pb-3 md:flex-col md:overflow-visible md:pb-0">
            {NAV.map(({ href, label, icon: Icon }) => {
              const active = pathname === href || pathname?.startsWith(`${href}/`);
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
                  {label}
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
              Log out
            </Button>
          </div>
        </aside>
        <main id="main-content" className="flex-1 p-4 sm:p-6 lg:p-10">
          <div className="mx-auto max-w-6xl">{children}</div>
        </main>
      </div>
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
