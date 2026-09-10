"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import { useLocale } from "@/i18n/context";

export interface WorkspaceNavTabsProps {
  workspaceId: string;
}

/** Simple two-link nav (Overview / Consent) shared by the hub and the existing
 *  consent page -- no Radix Tabs, no new layout file, active state from
 *  `usePathname()`. */
export function WorkspaceNavTabs({ workspaceId }: WorkspaceNavTabsProps) {
  const pathname = usePathname();
  const { t } = useLocale();

  const tabs = [
    { href: `/workspaces/${workspaceId}`, label: t("app.relationshipWorkspace.tabOverview") },
    { href: `/workspaces/${workspaceId}/dynamics`, label: t("app.relationshipWorkspace.tabDynamics") },
    { href: `/workspaces/${workspaceId}/consent`, label: t("app.relationshipWorkspace.tabConsent") },
  ];

  return (
    <nav className="mb-6 flex gap-1 border-b border-white/10">
      {tabs.map((tab) => {
        const active = pathname === tab.href;
        return (
          <Link
            key={tab.href}
            href={tab.href}
            aria-current={active ? "page" : undefined}
            className={cn(
              "border-b-2 px-3 py-2 text-sm font-medium transition-colors",
              active ? "border-gold text-ivory" : "border-transparent text-muted hover:text-text",
            )}
          >
            {tab.label}
          </Link>
        );
      })}
    </nav>
  );
}
