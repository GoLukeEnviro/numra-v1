import Link from "next/link";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { SharedBadge } from "@/components/workspace/shared-badge";
import { useLocale } from "@/i18n/context";
import { useAuth } from "@/lib/auth-context";
import { cn } from "@/lib/utils";
import type { DualProfileMemberOut } from "@/api/client";

/** Fixed, known core-number keys (canon-spec.md) -- iterated defensively so an
 *  unknown or missing key is skipped rather than crashing the render. */
const CORE_NUMBER_KEYS = [
  "life_path",
  "expression",
  "soul_urge",
  "personality",
  "maturity",
  "personal_year",
  "personal_month",
  "personal_day",
] as const;

const CORE_NUMBER_LABEL_KEYS: Record<(typeof CORE_NUMBER_KEYS)[number], string> = {
  life_path: "Life Path",
  expression: "Expression",
  soul_urge: "Soul Urge",
  personality: "Personality",
  maturity: "Maturity",
  personal_year: "Personal Year",
  personal_month: "Personal Month",
  personal_day: "Personal Day",
};

function isDisplayValueEntry(entry: unknown): entry is { display_value: string } {
  return (
    entry !== null &&
    typeof entry === "object" &&
    "display_value" in entry &&
    typeof (entry as { display_value: unknown }).display_value === "string"
  );
}

export interface DualProfileGridProps {
  workspaceId: string;
  members: DualProfileMemberOut[];
}

function OwnProfileCard({ member }: { member: DualProfileMemberOut }) {
  const { t } = useLocale();
  return (
    <Card className="border-gold/30">
      <CardHeader>
        <CardTitle className="text-base">{t("app.relationshipWorkspace.dualProfileSelfTitle")}</CardTitle>
      </CardHeader>
      <CardContent>
        <p className="mb-3 text-sm font-medium text-ivory">{member.display_name}</p>
        {member.core_numbers ? (
          <CoreNumberList coreNumbers={member.core_numbers} />
        ) : (
          <p className="text-sm text-muted">—</p>
        )}
      </CardContent>
    </Card>
  );
}

function CoreNumberList({ coreNumbers }: { coreNumbers: Record<string, unknown> }) {
  return (
    <dl className="grid grid-cols-2 gap-3">
      {CORE_NUMBER_KEYS.map((key) => {
        const entry = coreNumbers[key];
        if (!isDisplayValueEntry(entry)) return null;
        return (
          <div key={key}>
            <dt className="text-xs uppercase tracking-wider text-bronze">{CORE_NUMBER_LABEL_KEYS[key]}</dt>
            <dd className="font-serif text-lg text-gold">{entry.display_value}</dd>
          </div>
        );
      })}
    </dl>
  );
}

function CounterpartProfileCard({ workspaceId, member }: { workspaceId: string; member: DualProfileMemberOut }) {
  const { t } = useLocale();
  const hasFullProfile = member.self_person !== null && member.core_numbers !== null;

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between gap-3">
        <CardTitle className="text-base">{member.display_name}</CardTitle>
        <SharedBadge />
      </CardHeader>
      <CardContent>
        {hasFullProfile && member.core_numbers ? (
          <CoreNumberList coreNumbers={member.core_numbers} />
        ) : (
          <p className="text-sm text-muted">
            <strong className="text-ivory">{member.display_name}</strong>{" "}
            {t("app.relationshipWorkspace.dualProfileMissingConsentSuffix")}{" "}
            <Link href={`/workspaces/${workspaceId}/consent`} className="text-bronze hover:underline">
              {t("app.relationshipWorkspace.dualProfileMissingConsentLink")}
            </Link>
          </p>
        )}
      </CardContent>
    </Card>
  );
}

/** Two-card grid, one per `DualProfileMemberOut`. The counterpart side degrades
 *  gracefully (never an error) when consent hasn't been granted -- `self_person`/
 *  `core_numbers` simply come back `null`, per the backend contract. */
export function DualProfileGrid({ workspaceId, members }: DualProfileGridProps) {
  const { user } = useAuth();
  const { t } = useLocale();

  return (
    <section>
      <h2 className="mb-2 text-xs font-semibold uppercase tracking-wider text-bronze">
        {t("app.relationshipWorkspace.dualProfileEyebrow")}
      </h2>
      <div className={cn("grid grid-cols-1 gap-6 md:grid-cols-2")}>
        {members.map((member) =>
          member.user_id === user?.id ? (
            <OwnProfileCard key={member.user_id} member={member} />
          ) : (
            <CounterpartProfileCard key={member.user_id} workspaceId={workspaceId} member={member} />
          ),
        )}
      </div>
    </section>
  );
}
