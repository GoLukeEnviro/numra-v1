"use client";

import { useEffect } from "react";

/**
 * V1.5 Epic I: registers public/sw.js, which caches only immutable static assets
 * (see that file's own docstring) and never touches /api/* -- so this is safe to
 * register unconditionally, including for a signed-in session.
 */
export function RegisterServiceWorker() {
  useEffect(() => {
    if (typeof window === "undefined" || !("serviceWorker" in navigator)) return;
    navigator.serviceWorker.register("/sw.js").catch(() => {
      // Registration can fail in private browsing or under some CSPs -- the app
      // works fully without it, so there is nothing to surface to the user.
    });
  }, []);

  return null;
}
