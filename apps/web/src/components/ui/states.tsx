import type { ReactNode } from "react";
import { Loader2, AlertTriangle, Inbox } from "lucide-react";
import { ApiError } from "@/api/client";
import { Button } from "@/components/ui/button";

export function LoadingState({ label = "Loading…" }: { label?: string }) {
  return (
    <div
      role="status"
      aria-live="polite"
      className="flex flex-col items-center justify-center gap-3 rounded-xl border border-white/10 bg-surface p-12 text-muted"
    >
      <Loader2 className="h-6 w-6 animate-spin text-gold" aria-hidden="true" />
      <span className="text-sm">{label}</span>
    </div>
  );
}

export function EmptyState({
  title,
  description,
  action,
}: {
  title: string;
  description?: string;
  action?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center gap-3 rounded-xl border border-dashed border-white/15 bg-surface/60 p-12 text-center">
      <Inbox className="h-6 w-6 text-muted" aria-hidden="true" />
      <h3 className="font-serif text-lg text-ivory">{title}</h3>
      {description && <p className="max-w-md text-sm text-muted">{description}</p>}
      {action}
    </div>
  );
}

export function ErrorState({
  error,
  onRetry,
  title = "Something went wrong",
}: {
  error: unknown;
  onRetry?: () => void;
  title?: string;
}) {
  const message =
    error instanceof ApiError
      ? error.message
      : error instanceof Error
        ? error.message
        : "An unexpected error occurred.";
  const code = error instanceof ApiError ? error.code : undefined;

  return (
    <div
      role="alert"
      className="flex flex-col items-start gap-3 rounded-xl border border-danger/30 bg-danger-surface p-6"
    >
      <div className="flex items-center gap-2 text-danger">
        <AlertTriangle className="h-5 w-5" aria-hidden="true" />
        <h3 className="font-serif text-base">{title}</h3>
      </div>
      <p className="text-sm text-text">
        {code && <span className="mr-2 rounded bg-black/20 px-1.5 py-0.5 font-mono text-xs">{code}</span>}
        {message}
      </p>
      {onRetry && (
        <Button variant="secondary" size="sm" onClick={onRetry}>
          Try again
        </Button>
      )}
    </div>
  );
}
