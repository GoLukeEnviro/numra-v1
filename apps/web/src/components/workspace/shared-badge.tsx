import { Users } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { useLocale } from "@/i18n/context";

/** Marks the counterpart side of a `DualProfileMemberOut` card in the Relationship
 *  Workspace -- signals "this is the other person's side, shared through the
 *  connection", the mirror image of `PrivateBadge` on the Personal Workspace. */
export function SharedBadge() {
  const { t } = useLocale();
  return (
    <Badge variant="shared">
      <Users className="h-3 w-3" aria-hidden="true" />
      {t("workspace.sharedLabel")}
    </Badge>
  );
}
