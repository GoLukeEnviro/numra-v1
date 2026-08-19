import Link, { type LinkProps } from "next/link";
import type { AnchorHTMLAttributes } from "react";
import { buttonVariants } from "@/components/ui/button";
import type { VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

export interface LinkButtonProps
  extends LinkProps,
    Omit<AnchorHTMLAttributes<HTMLAnchorElement>, keyof LinkProps>,
    VariantProps<typeof buttonVariants> {}

/** A `<Link>` styled as a Button — never nest a real <button> inside an <a>. */
export function LinkButton({ className, variant, size, ...props }: LinkButtonProps) {
  return <Link className={cn(buttonVariants({ variant, size }), className)} {...props} />;
}
