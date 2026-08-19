import type { HTMLAttributes } from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium",
  {
    variants: {
      variant: {
        // Neutral outline — general-purpose small tag.
        neutral: "border border-white/15 text-muted",
        // Master Number — filled gold, matches the design brief's key accent.
        master: "bg-gold text-background font-semibold",
        // Karmic Debt — filled plum. Plum fails AA as small text directly on the
        // page background, so it is only ever used as a filled surface here,
        // paired with ivory text (contrast ~6.5:1).
        karmic: "bg-plum text-ivory font-semibold",
        // Diagnostic / non-canonical — dashed outline, deliberately muted so it
        // never reads as equal weight to a canonical value.
        diagnostic: "border border-dashed border-muted/60 text-muted",
        success: "border border-success/40 text-success",
      },
    },
    defaultVariants: {
      variant: "neutral",
    },
  },
);

export interface BadgeProps
  extends HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof badgeVariants> {}

export function Badge({ className, variant, ...props }: BadgeProps) {
  return <span className={cn(badgeVariants({ variant }), className)} {...props} />;
}
