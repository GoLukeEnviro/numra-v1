"use client";

import { Badge } from "@/components/ui/badge";
import { useLocale } from "@/i18n/context";

/**
 * The canonical role code stays the visible text — `USER` / `ADMIN` are internal
 * identifiers the backend and the audit log speak, and translating them away would
 * make the console disagree with its own data. The localized wording rides along as
 * the tooltip instead.
 */
export function RoleBadge({ role }: { role: string }) {
  const { t } = useLocale();
  const label = role === "ADMIN" ? t("admin.users.roleAdminLabel") : t("admin.users.roleUserLabel");
  return (
    <Badge variant={role === "ADMIN" ? "master" : "neutral"} title={label}>
      {role}
    </Badge>
  );
}

export function StatusBadge({ isActive }: { isActive: boolean }) {
  const { t } = useLocale();
  return (
    <Badge variant={isActive ? "success" : "diagnostic"}>
      {isActive ? t("admin.users.statusActive") : t("admin.users.statusDisabled")}
    </Badge>
  );
}
