import type { de } from "@/i18n/messages/de";
import { enAdmin } from "@/i18n/messages/en/admin";
import { enApp } from "@/i18n/messages/en/app";
import { enCore } from "@/i18n/messages/en/core";
import { enPublic } from "@/i18n/messages/en/public";

/**
 * English is switchable via Settings (V1.5 Epic G). Typed against `de`'s key set so
 * a missing or extra key fails `tsc`, not a runtime lookup. Module split mirrors
 * `messages/de/` exactly — see that file's note.
 */
export const en: Record<keyof typeof de, string> = {
  ...enCore,
  ...enPublic,
  ...enApp,
  ...enAdmin,
};
