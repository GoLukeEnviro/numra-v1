import { Lock } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { useLocale } from "@/i18n/context";

/** Section-level marker for the three private Personal Workspace panels (Notes,
 *  Reflections, Tasks) -- signals "only visible to you", never rendered as part of
 *  the shared/public profile surfaces. */
export function PrivateBadge() {
  const { t } = useLocale();
  return (
    <Badge variant="private">
      <Lock className="h-3 w-3" aria-hidden="true" />
      {t("workspace.privateLabel")}
    </Badge>
  );
}
