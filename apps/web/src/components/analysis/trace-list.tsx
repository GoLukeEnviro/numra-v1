import type { TraceStep } from "@/lib/trace";
import { cn } from "@/lib/utils";

export function TraceList({ steps, className }: { steps: TraceStep[]; className?: string }) {
  if (steps.length === 0) {
    return <p className="text-sm text-muted">No trace steps recorded.</p>;
  }
  return (
    <ol className={cn("flex flex-col gap-1.5", className)}>
      {steps.map((step, i) => (
        <li key={step.key} className="flex items-start gap-2.5 text-sm">
          <span className="mt-0.5 shrink-0 rounded-full bg-surface-2 px-1.5 py-0.5 text-[10px] text-muted">
            {i + 1}
          </span>
          <code className="font-mono text-text">{step.text}</code>
        </li>
      ))}
    </ol>
  );
}
