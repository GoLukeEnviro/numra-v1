import { cn } from "@/lib/utils";

/**
 * Numra brand marks — the "constructed N": three straight lines ending in four
 * nodes. Geometry and symbolism are specified in docs/brand/visual-identity.md
 * §2. Keep this component in sync with src/app/icon.svg.
 */
const N_STROKES = ["M10.5 21.5V10.5", "M10.5 10.5L21.5 21.5", "M21.5 10.5V21.5"];

const NODES = [
  { x: 10.5, y: 10.5 },
  { x: 10.5, y: 21.5 },
  { x: 21.5, y: 10.5 },
  { x: 21.5, y: 21.5 },
];

export function BrandMark({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 32 32"
      className={className}
      aria-hidden="true"
      focusable="false"
    >
      <rect width="32" height="32" rx="7" fill="#0B0B0F" />
      <g stroke="#C8A96B" strokeWidth="2" fill="none">
        {N_STROKES.map((d) => (
          <path key={d} d={d} />
        ))}
      </g>
      <g fill="#F2EBDD">
        {NODES.map(({ x, y }) => (
          <circle key={`${x}-${y}`} cx={x} cy={y} r="1.6" />
        ))}
      </g>
    </svg>
  );
}

/**
 * Emblem + wordmark with the signature node dot. Size via className props —
 * there is deliberately no size variant system: each call site owns its scale.
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
        Numra
      </span>
      <span
        aria-hidden="true"
        className="h-1.5 w-1.5 shrink-0 self-center rounded-full bg-gold"
      />
    </span>
  );
}
