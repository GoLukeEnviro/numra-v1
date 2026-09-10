import type { ReactNode } from "react";
import { Loader2, AlertTriangle, Inbox, Clock, Lock, Sparkles } from "lucide-react";
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

/**
 * Backend errors the V2 frontend needs to recognize (specs/v2/api-contract.md):
 * all five are *expected*, phase-gated states -- not failures -- so they must never
 * render through ErrorState's alarming, red "something went wrong" treatment.
 */
export type PhaseErrorCode =
  | "V2_DISABLED"
  | "V2_PHASE_DISABLED"
  | "WORKSPACE_DISSOLVED"
  | "KNOWLEDGE_FRAME_NOT_AVAILABLE"
  | "CONSENT_NOT_GRANTED"
  // PR-WEB-05: relationship/shadow analysis pre-conditions. Both are expected,
  // resolvable setup states (pick a relationship type; complete a self profile) --
  // not failures, so they render calm like the others, not through ErrorState.
  | "RELATIONSHIP_TYPE_NOT_SET"
  | "SELF_PROFILE_REQUIRED";

const PHASE_DISABLED_ICONS: Record<PhaseErrorCode, typeof Clock> = {
  V2_DISABLED: Clock,
  V2_PHASE_DISABLED: Clock,
  WORKSPACE_DISSOLVED: Clock,
  KNOWLEDGE_FRAME_NOT_AVAILABLE: Clock,
  CONSENT_NOT_GRANTED: Lock,
  RELATIONSHIP_TYPE_NOT_SET: Clock,
  SELF_PROFILE_REQUIRED: Clock,
};

export interface PhaseDisabledStateProps {
  code: PhaseErrorCode;
  title: string;
  description?: string;
  action?: ReactNode;
}

/**
 * One generic component for all five phase-gated codes -- copy comes from the
 * caller, not five near-identical special-case components. Visually calm (same
 * neutral surface as EmptyState, `role="status"` not "alert"): no danger border, no
 * AlertTriangle, and deliberately no retry prop -- a phase gate does not resolve by
 * clicking "try again".
 */
export function PhaseDisabledState({ code, title, description, action }: PhaseDisabledStateProps) {
  const Icon = PHASE_DISABLED_ICONS[code];
  return (
    <div
      role="status"
      className="flex flex-col items-center gap-3 rounded-xl border border-white/10 bg-surface p-12 text-center"
    >
      <Icon className="h-6 w-6 text-muted" aria-hidden="true" />
      <h3 className="font-serif text-lg text-ivory">{title}</h3>
      {description && <p className="max-w-md text-sm text-muted">{description}</p>}
      {action}
    </div>
  );
}

export function isPhaseDisabledError(
  error: unknown,
): error is ApiError & { code: PhaseErrorCode } {
  return (
    error instanceof ApiError &&
    (
      [
        "V2_DISABLED",
        "V2_PHASE_DISABLED",
        "WORKSPACE_DISSOLVED",
        "KNOWLEDGE_FRAME_NOT_AVAILABLE",
        "CONSENT_NOT_GRANTED",
        "RELATIONSHIP_TYPE_NOT_SET",
        "SELF_PROFILE_REQUIRED",
      ] as const
    ).includes(error.code as PhaseErrorCode)
  );
}

/** Feature not built yet (PR-WEB-00 placeholder routes) -- visually near EmptyState,
 *  but a Sparkles icon rather than Inbox: nothing is missing here, it just doesn't
 *  exist yet. */
export function ComingSoonState({
  title,
  description,
}: {
  title: string;
  description: string;
}) {
  return (
    <div className="flex flex-col items-center gap-3 rounded-xl border border-dashed border-white/15 bg-surface/60 p-12 text-center">
      <Sparkles className="h-6 w-6 text-gold" aria-hidden="true" />
      <h3 className="font-serif text-lg text-ivory">{title}</h3>
      <p className="max-w-md text-sm text-muted">{description}</p>
    </div>
  );
}
