"use client";

import { useRef, useState } from "react";
import { ApiError, type RegenerationPreviewOut } from "@/api/client";
import { newIdempotencyKey } from "@/lib/idempotency";
import { useLocale } from "@/i18n/context";

type Phase =
  | { name: "idle" }
  | { name: "loading" }
  | { name: "ready"; preview: RegenerationPreviewOut }
  | { name: "starting"; preview: RegenerationPreviewOut };

/**
 * D6: the explicit "Neu erzeugen" control for a flagged result. Nothing happens on its own:
 * the first click only loads the preview (what the click would cost), the second click
 * starts the regeneration. The Idempotency-Key lives for the whole dialog, so a double
 * click or a retry after a lost response re-joins the same job instead of starting another.
 */
export function RegenerateControl<T extends { id: string }>({
  loadPreview,
  start,
  onStarted,
  onOpenExisting,
}: {
  loadPreview: () => Promise<RegenerationPreviewOut>;
  start: (idempotencyKey: string) => Promise<T>;
  onStarted: (started: T) => void;
  onOpenExisting: (id: string) => void;
}) {
  const { t } = useLocale();
  const [phase, setPhase] = useState<Phase>({ name: "idle" });
  const [error, setError] = useState<{ code: string; message: string } | null>(null);
  const keyRef = useRef<string | null>(null);
  const inFlight = useRef(false);

  function describe(err: unknown): { code: string; message: string } {
    return err instanceof ApiError
      ? { code: err.code, message: err.message }
      : { code: "NETWORK_ERROR", message: t("common.networkError") };
  }

  async function open() {
    setError(null);
    setPhase({ name: "loading" });
    try {
      setPhase({ name: "ready", preview: await loadPreview() });
    } catch (err) {
      setError(describe(err));
      setPhase({ name: "idle" });
    }
  }

  async function confirm(preview: RegenerationPreviewOut) {
    if (inFlight.current) return;
    inFlight.current = true;
    setError(null);
    setPhase({ name: "starting", preview });
    keyRef.current = keyRef.current ?? newIdempotencyKey();
    try {
      const started = await start(keyRef.current);
      keyRef.current = null;
      onStarted(started);
    } catch (err) {
      setError(describe(err));
      setPhase({ name: "ready", preview });
    } finally {
      inFlight.current = false;
    }
  }

  const errorBox = error && (
    <div
      role="alert"
      className="rounded-lg border border-danger/30 bg-danger-surface p-3 text-sm text-text"
    >
      <span className="mr-1.5 rounded bg-black/25 px-1.5 py-0.5 font-mono text-xs">
        {error.code}
      </span>
      {error.message}
    </div>
  );

  if (phase.name === "idle" || phase.name === "loading") {
    return (
      <div className="flex flex-col gap-3">
        <div>
          <button
            type="button"
            onClick={() => void open()}
            disabled={phase.name === "loading"}
            className="rounded-lg border border-gold/50 px-3 py-1.5 text-sm text-gold transition-colors hover:bg-gold/10 disabled:opacity-60"
          >
            {phase.name === "loading" ? t("app.regenerate.loading") : t("app.regenerate.action")}
          </button>
        </div>
        {errorBox}
      </div>
    );
  }

  const { preview } = phase;
  const starting = phase.name === "starting";
  const quota = preview.quota;

  return (
    <div className="flex flex-col gap-3" data-testid="regenerate-preview">
      {preview.blocked_reason === "ALREADY_REGENERATED" && preview.existing_regeneration_id ? (
        <div className="flex flex-col gap-2 text-sm text-text">
          <p>{t("app.regenerate.already")}</p>
          <div>
            <button
              type="button"
              onClick={() => onOpenExisting(preview.existing_regeneration_id as string)}
              className="rounded-lg border border-gold/50 px-3 py-1.5 text-sm text-gold hover:bg-gold/10"
            >
              {t("app.regenerate.openExisting")}
            </button>
          </div>
        </div>
      ) : preview.blocked_reason === "NOT_FLAGGED" ? (
        <p className="text-sm text-text">{t("app.regenerate.notFlagged")}</p>
      ) : (
        <>
          <ul className="list-disc space-y-1 pl-5 text-sm text-text">
            {preview.uses_llm && <li>{t("app.regenerate.previewLlm")}</li>}
            <li>{t("app.regenerate.previewUsage")}</li>
            {quota && quota.window_limit !== null && (
              <li>
                {t("app.regenerate.previewQuota")
                  .replace("{used}", String(quota.used_in_window))
                  .replace("{limit}", String(quota.window_limit))}
              </li>
            )}
            {preview.original_kept && <li>{t("app.regenerate.previewOriginal")}</li>}
          </ul>
          {quota?.would_exceed && (
            <p role="status" className="text-sm text-text">
              {t("app.regenerate.exceeded")}
            </p>
          )}
          {errorBox}
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => void confirm(preview)}
              disabled={starting || quota?.would_exceed === true}
              className="rounded-lg bg-gold px-3 py-1.5 text-sm font-medium text-background disabled:opacity-60"
            >
              {starting ? t("app.regenerate.confirming") : t("app.regenerate.confirm")}
            </button>
            <button
              type="button"
              onClick={() => setPhase({ name: "idle" })}
              disabled={starting}
              className="rounded-lg border border-white/15 px-3 py-1.5 text-sm text-muted hover:text-text disabled:opacity-60"
            >
              {t("app.regenerate.cancel")}
            </button>
          </div>
        </>
      )}
    </div>
  );
}
