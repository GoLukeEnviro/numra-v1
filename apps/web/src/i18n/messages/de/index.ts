import { deAdmin } from "@/i18n/messages/de/admin";
import { deApp } from "@/i18n/messages/de/app";
import { deCore } from "@/i18n/messages/de/core";
import { dePublic } from "@/i18n/messages/de/public";

/**
 * German is Numra's default UI language (V1.5 Epic G) — this is the catalog loaded
 * when no locale preference has been chosen yet. V1.6 B split it into per-surface
 * modules (core chrome / public pages / signed-in product / admin console) because a
 * single flat file had grown past the point where two people could extend different
 * surfaces without colliding. `en` mirrors this key set 1:1; `i18n/catalog.ts`
 * enforces that at the type level, and `__tests__/catalog-parity.test.ts` at runtime.
 */
export const de = { ...deCore, ...dePublic, ...deApp, ...deAdmin };
