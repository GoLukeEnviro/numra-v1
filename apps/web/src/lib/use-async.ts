"use client";

import { useCallback, useEffect, useRef, useState } from "react";

export type AsyncState<T> =
  | { status: "loading" }
  | { status: "error"; error: unknown }
  | { status: "success"; data: T };

/**
 * Small fetch-on-mount hook shared by every data page so loading / error /
 * success states behave consistently across the app. `deps` re-triggers the
 * fetch (e.g. when a route param changes).
 */
export function useAsync<T>(fn: () => Promise<T>, deps: unknown[]): AsyncState<T> & {
  reload: () => void;
} {
  const [state, setState] = useState<AsyncState<T>>({ status: "loading" });
  const fnRef = useRef(fn);
  fnRef.current = fn;
  const [tick, setTick] = useState(0);

  const reload = useCallback(() => setTick((t) => t + 1), []);

  useEffect(() => {
    let cancelled = false;
    setState({ status: "loading" });
    fnRef
      .current()
      .then((data) => {
        if (!cancelled) setState({ status: "success", data });
      })
      .catch((error: unknown) => {
        if (!cancelled) setState({ status: "error", error });
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, tick]);

  return { ...state, reload };
}
