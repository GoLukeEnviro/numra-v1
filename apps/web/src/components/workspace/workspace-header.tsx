"use client";

import { useRouter } from "next/navigation";
import { NumericWheel } from "@/components/layout/numeric-wheel";
import { WorkspaceSwitcher } from "@/components/workspaces/workspace-switcher";
import { peopleToWorkspaceOptions } from "@/components/workspaces/workspace-switcher-personal";
import type { PersonOut } from "@/api/client";
import { personDisplayName } from "@/lib/identity";
import { useLocale } from "@/i18n/context";

function profileTypeLabel(person: PersonOut, t: (key: "workspace.selfProfileLabel" | "workspace.managedProfileLabel") => string): string {
  return person.person_account_mode === "SELF" ? t("workspace.selfProfileLabel") : t("workspace.managedProfileLabel");
}

export interface WorkspaceHeaderProps {
  person: PersonOut;
  people: PersonOut[];
}

/** Header for the Personal Workspace hub: eyebrow + person name + self/managed
 *  badge, plus the WorkspaceSwitcher to jump straight to another person's hub. */
export function WorkspaceHeader({ person, people }: WorkspaceHeaderProps) {
  const router = useRouter();
  const { t } = useLocale();
  const options = peopleToWorkspaceOptions(people, (p) => profileTypeLabel(p, t));

  return (
    <header className="sacred-wheel-bg-left relative mb-8 overflow-hidden rounded-xl border border-white/10 bg-surface p-6 shadow-elevated sm:p-8">
      <NumericWheel className="pointer-events-none absolute -right-16 -top-20 h-56 w-56 opacity-[0.12]" />
      <div className="relative flex flex-wrap items-end justify-between gap-6">
        <div className="min-w-0">
          <p className="mb-2 text-xs uppercase tracking-wider text-bronze">{t("app.workspace.eyebrow")}</p>
          <div className="flex flex-wrap items-center gap-3">
            <h1 className="font-serif text-3xl text-ivory sm:text-4xl">{personDisplayName(person)}</h1>
            <span className="rounded-full border border-white/15 px-2.5 py-0.5 text-xs text-muted">
              {profileTypeLabel(person, t)}
            </span>
          </div>
        </div>
        {people.length > 1 && (
          <WorkspaceSwitcher
            className="w-full sm:w-72"
            options={options}
            activeId={person.id}
            onSelect={(id) => router.push(`/people/${id}/workspace`)}
          />
        )}
      </div>
    </header>
  );
}
