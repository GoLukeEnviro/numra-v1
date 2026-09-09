import { cn } from "@/lib/utils";
import { BRAND_NAME } from "@/lib/brand";

/**
 * AVENYTH brand marks — the "constructed A": two diverging legs (two
 * individuals) joined by a crossbar at ~61% height (the shared moment during
 * the journey, not only at the end). Geometry and symbolism are specified in
 * docs/brand/visual-identity.md. Keep this component in sync with
 * src/app/icon.svg.
 */
const A_LEGS = [
  { x1: 16, y1: 7, x2: 9, y2: 25 },
  { x1: 16, y1: 7, x2: 23, y2: 25 },
];

const CROSSBAR = { x1: 11.72, y1: 18, x2: 20.28, y2: 18 };

const APEX_NODES = [
  { x: 16, y: 7 },
  { x: 9, y: 25 },
  { x: 23, y: 25 },
];

const CROSSBAR_NODES = [
  { x: 11.72, y: 18 },
  { x: 20.28, y: 18 },
];

export function BrandMark({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 32 32"
      className={className}
      aria-hidden="true"
      focusable="false"
    >
      <rect x="0" y="0" width="32" height="32" rx="7" fill="#0B0B0F" />
      <g stroke="#C8A96B" strokeWidth="1.4" strokeLinecap="round">
        {A_LEGS.map(({ x1, y1, x2, y2 }) => (
          <line key={`${x1}-${y1}-${x2}-${y2}`} x1={x1} y1={y1} x2={x2} y2={y2} />
        ))}
        <line
          x1={CROSSBAR.x1}
          y1={CROSSBAR.y1}
          x2={CROSSBAR.x2}
          y2={CROSSBAR.y2}
        />
      </g>
      <g fill="#F2EBDD">
        {APEX_NODES.map(({ x, y }) => (
          <circle key={`${x}-${y}`} cx={x} cy={y} r="1.3" />
        ))}
      </g>
      <g fill="#604B72">
        {CROSSBAR_NODES.map(({ x, y }) => (
          <circle key={`${x}-${y}`} cx={x} cy={y} r="1.6" />
        ))}
      </g>
    </svg>
  );
}

/**
 * Emblem + wordmark with the signature crossbar nodes. Size via className
 * props — there is deliberately no size variant system: each call site owns
 * its scale.
 */
export function Logo({
  className,
  markClassName,
  textClassName,
}: {
  className?: string;
  markClassName?: string;
  textClassName?: string;
}) {
  return (
    <span className={cn("inline-flex items-center gap-2.5", className)}>
      <BrandMark className={cn("h-7 w-7 shrink-0", markClassName)} />
      <span className={cn("font-serif leading-none text-ivory", textClassName)}>
        {BRAND_NAME}
      </span>
      <span
        aria-hidden="true"
        className="h-1.5 w-1.5 shrink-0 self-center rounded-full bg-gold"
      />
    </span>
  );
}
