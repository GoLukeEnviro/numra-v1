"use client";

import { Component, type ReactNode } from "react";
import { AlertTriangle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useLocale } from "@/i18n/context";

/**
 * React only supports catching render errors via a class component's
 * `getDerivedStateFromError`/`componentDidCatch` -- no hook equivalent exists. This
 * wraps one content region (Copilot, a workspace view, …) so a bug there shows a
 * small inline fallback instead of taking down the whole page and falling through to
 * the route-level `app/error.tsx`/`global-error.tsx`.
 */
function Fallback({ onRetry }: { onRetry: () => void }) {
  const { t } = useLocale();
  return (
    <div
      role="alert"
      className="flex flex-col items-start gap-3 rounded-xl border border-danger/30 bg-danger-surface p-6"
    >
      <div className="flex items-center gap-2 text-danger">
        <AlertTriangle className="h-5 w-5" aria-hidden="true" />
        <h3 className="font-serif text-base">{t("common.somethingWrong")}</h3>
      </div>
      <Button variant="secondary" size="sm" onClick={onRetry}>
        {t("common.tryAgain")}
      </Button>
    </div>
  );
}

export class ErrorBoundary extends Component<{ children: ReactNode }, { hasError: boolean }> {
  state = { hasError: false };

  static getDerivedStateFromError() {
    return { hasError: true };
  }

  componentDidCatch(error: unknown) {
    // eslint-disable-next-line no-console -- no client-side error reporting pipeline exists yet; this keeps the crash visible in dev/CI logs instead of disappearing silently.
    console.error("ErrorBoundary caught a render error", error);
  }

  reset = () => this.setState({ hasError: false });

  render() {
    if (this.state.hasError) return <Fallback onRetry={this.reset} />;
    return this.props.children;
  }
}
